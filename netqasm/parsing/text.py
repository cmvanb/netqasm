from itertools import count
from collections import defaultdict

from netqasm.string_util import group_by_word, is_variable_name, is_number
from netqasm.util import NetQASMSyntaxError, NetQASMInstrError
from netqasm.encoding import RegisterName, REG_INDEX_BITS
from netqasm.subroutine import (
    Constant,
    Label,
    Register,
    Address,
    ArrayEntry,
    ArraySlice,
    Command,
    BranchLabel,
    Subroutine,
    Symbols,
)
from netqasm.instructions import Instruction, string_to_instruction


def parse_text_subroutine(
    subroutine,
    assign_branch_labels=True,
    make_args_operands=True,
    replace_constants=True,
    # expand_slices=True,
):
    """Parses a subroutine and splits the preamble and body into separate parts."""
    preamble_lines, body_lines = _split_preamble_body(subroutine)
    preamble_data = _parse_preamble(preamble_lines)
    body_lines = _apply_macros(body_lines, preamble_data[Symbols.PREAMBLE_DEFINE])
    subroutine = _create_subroutine(preamble_data, body_lines)
    subroutine = assemble_subroutine(
        subroutine=subroutine,
        assign_branch_labels=assign_branch_labels,
        make_args_operands=make_args_operands,
        replace_constants=replace_constants,
        # expand_slices=expand_slices,
    )
    return subroutine


def assemble_subroutine(
    subroutine,
    assign_branch_labels=True,
    make_args_operands=True,
    replace_constants=True,
    # expand_slices=True,
):
    if make_args_operands:
        _make_args_operands(subroutine)
    # if expand_slices:
    #     _expand_slices(subroutine)
    if replace_constants:
        _replace_constants(subroutine)
        # _replace_explicit_addresses(subroutine, current_registers)
    if assign_branch_labels:
        _assign_branch_labels(subroutine)
    return subroutine


def _create_subroutine(preamble_data, body_lines):
    commands = []
    for line in body_lines:
        if line.endswith(Symbols.BRANCH_END):
            # A command defining a branch label should end with BRANCH_END
            branch_label = line.rstrip(Symbols.BRANCH_END)
            if not is_variable_name(branch_label):
                raise NetQASMSyntaxError(f"The branch label {branch_label} is not a valid label")
            commands.append(BranchLabel(branch_label))
        else:
            words = group_by_word(line, brackets=Symbols.ARGS_BRACKETS)
            instr_name, args = _split_instr_and_args(words[0])
            instr = string_to_instruction(instr_name)
            args = _parse_args(args)
            operands = _parse_operands(words[1:])
            command = Command(
                instruction=instr,
                args=args,
                operands=operands,
            )
            commands.append(command)

    return Subroutine(
        netqasm_version=_parse_netqasm_version(preamble_data[Symbols.PREAMBLE_NETQASM][0][0]),
        app_id=int(preamble_data[Symbols.PREAMBLE_APPID][0][0]),
        commands=commands,
    )


def _parse_netqasm_version(netqasm_version):
    try:
        major, minor = netqasm_version.strip().split('.')
        return int(major), int(minor)
    except Exception as err:
        raise ValueError(f"Could not parse netqasm version {netqasm_version} since: {err}")


def _split_instr_and_args(word):
    instr, args = _split_of_bracket(word, brackets=Symbols.ARGS_BRACKETS)
    return instr, args


def _parse_args(args):
    if args == "":
        return []
    else:
        return [_parse_constant(arg.strip())
                for arg in args.strip(Symbols.ARGS_BRACKETS)
                .split(Symbols.ARGS_DELIM)]


def _parse_constant(constant, return_int=False):
    if not is_number(constant):
        raise NetQASMSyntaxError(f"Expected constant, got {constant}")
    if return_int:
        return int(constant)
    return Constant(int(constant))


def _parse_operands(words):
    operands = []
    for word in words:
        operand = _parse_operand(word.strip())
        operands.append(operand)

    return operands


def _parse_operand(word):
    if word.startswith(Symbols.ADDRESS_START):
        return parse_address(word)
    else:
        return _parse_value(word, allow_label=True)


def _parse_value(value, allow_label=False):
    # Try to parse a constant
    try:
        return _parse_constant(value)
    except NetQASMSyntaxError:
        pass

    # Try to parse a register
    try:
        return parse_register(value)
    except NetQASMSyntaxError:
        pass

    if allow_label:
        # Parse a label
        return _parse_label(value)
    else:
        raise NetQASMSyntaxError("{value} is not a valid value in this case")


def _parse_label(label):
    return Label(label)


_REGISTER_NAMES = {reg.name: reg for reg in RegisterName}


def parse_register(register):
    try:
        register_name = _REGISTER_NAMES[register[0]]
    except KeyError:
        raise NetQASMSyntaxError(f"{register[0]} is not a valid register name")
    value = _parse_constant(register[1:], return_int=True)
    return Register(register_name, value)


def parse_address(address):
    base_address, index = _split_of_bracket(address, Symbols.INDEX_BRACKETS)
    base_address = _parse_base_address(base_address)
    index = _parse_index(index)
    address = Address(base_address)
    if index is None:
        return address
    elif isinstance(index, tuple):
        return ArraySlice(address, start=index[0], stop=index[1])
    else:
        return ArrayEntry(address, index)


def _parse_base_address(base_address):
    if not base_address.startswith(Symbols.ADDRESS_START):
        raise NetQASMSyntaxError(f"Expected address, got {base_address}")
    return _parse_value(base_address.lstrip(Symbols.ADDRESS_START))


def _parse_index(index):
    if index == "":
        return None
    index = index.strip(Symbols.INDEX_BRACKETS).strip()
    if Symbols.SLICE_DELIM in index:
        # if index == Symbols.SLICE_DELIM:
        #     return None, None
        # elif index.startswith(Symbols.SLICE_DELIM):
        #     stop = index.lstrip(Symbols.SLICE_DELIM)
        #     return None, _parse_value(stop.strip())
        # elif index.endswith(Symbols.SLICE_DELIM):
        #     start = index.rstrip(Symbols.SLICE_DELIM)
        #     return _parse_value(start.strip()), None
        # else:
        start, stop = index.split(Symbols.SLICE_DELIM)
        return _parse_value(start.strip()), _parse_value(stop.strip())
    else:
        return _parse_value(index)


def _split_of_bracket(word, brackets):
    start_bracket, end_bracket = brackets
    start = word.find(start_bracket)
    if start == -1:
        return word, ""
    if word[-1] != end_bracket:
        raise NetQASMSyntaxError(f"No end bracket in {word}, expected '{end_bracket}'")
    address = word[:start]
    content = word[start:]
    return address, content


# def _parse_value(word):
#     if word.startswith(Symbols.DEREF_START):
#         address = word.lstrip(Symbols.INDIRECT_START)
#         if is_number(address):
#             address = int(address)
#         return Address(address=address, mode=AddressMode.INDIRECT)
#     elif word.startswith(Symbols.ADDRESS_START):
#         address = word.lstrip(Symbols.ADDRESS_START)
#         if not is_number(address):
#             raise NetQASMSyntaxError(f"Expected number for address {address}")
#         return Address(address=int(address), mode=AddressMode.DIRECT)
#     elif is_number(word):
#         return Address(address=int(word), mode=AddressMode.IMMEDIATE)
#     else:
#         # Direct mode with a variable
#         return Address(address=word, mode=AddressMode.DIRECT)


def _split_preamble_body(subroutine):
    """Splits the preamble from the body of the subroutine"""
    is_preamble = True
    preamble_lines = []
    body_lines = []
    for line in subroutine.split('\n'):
        # Remove surrounding whitespace and comments
        line = line.strip()
        line = _remove_comments_from_line(line)
        if line == '':  # Ignore empty lines
            continue
        if line.startswith(Symbols.PREAMBLE_START):
            if not is_preamble:  # Should not go out of preamble and in again
                raise NetQASMSyntaxError("Cannot have a preamble line after instructions")
            line = line.lstrip(Symbols.PREAMBLE_START).strip()
            if line == Symbols.PREAMBLE_START:  # Ignore lines with only a '#' character
                continue
            preamble_lines.append(line)
        else:
            is_preamble = False  # From now on the lines should not be part of the preamble
            body_lines.append(line)
    return preamble_lines, body_lines


def _apply_macros(body_lines, macros):
    """Applies macros to the body lines"""
    if len(body_lines) == 0:
        return []
    body = "\n".join(body_lines)
    for macro_key, macro_value in macros:
        macro_value = macro_value.strip(Symbols.PREAMBLE_DEFINE_BRACKETS)
        body = body.replace(f"{macro_key}{Symbols.MACRO_END}", macro_value)
    return list(body.split('\n'))


def _remove_comments_from_line(line):
    """Removes comments from a line"""
    return line.split(Symbols.COMMENT_START)[0]


def _parse_preamble(preamble_lines):
    """Parses the preamble lines"""

    preamble_instructions = defaultdict(list)
    for line in preamble_lines:
        try:
            instr, *operands = group_by_word(line, brackets=Symbols.PREAMBLE_DEFINE_BRACKETS)
        except ValueError as err:
            raise NetQASMSyntaxError(f"Could not parse preamble instruction, since: {err}")
        preamble_instructions[instr].append(operands)
    _assert_valid_preamble_instructions(preamble_instructions)
    return preamble_instructions


def _assert_valid_preamble_instructions(preamble_instructions):
    preamble_assertions = {
        Symbols.PREAMBLE_NETQASM: _assert_valid_preamble_instr_netqasm,
        Symbols.PREAMBLE_APPID: _assert_valid_preamble_instr_appid,
        Symbols.PREAMBLE_DEFINE: _assert_valid_preamble_instr_define,
    }
    for instr, list_of_operands in preamble_instructions.items():
        preamble_assertion = preamble_assertions.get(instr)
        if preamble_assertion is None:
            raise NetQASMInstrError(f"The instruction {instr} is not a valid preamble instruction")
        preamble_assertion(list_of_operands)


def _assert_valid_preamble_instr_netqasm(list_of_operands):
    _assert_single_preamble_instr(list_of_operands, Symbols.PREAMBLE_NETQASM)
    _assert_single_preamble_arg(list_of_operands, Symbols.PREAMBLE_NETQASM)


def _assert_valid_preamble_instr_appid(list_of_operands):
    _assert_single_preamble_instr(list_of_operands, Symbols.PREAMBLE_APPID)
    _assert_single_preamble_arg(list_of_operands, Symbols.PREAMBLE_APPID)


def _assert_valid_preamble_instr_define(list_of_operands):
    macro_keys = []
    for operands in list_of_operands:
        if len(operands) != 2:
            raise NetQASMSyntaxError(f"Preamble instruction {Symbols.PREAMBLE_DEFINE} should contain "
                                     "exactly two argument, "
                                     f"not {len(operands)} as in '{operands}'")
        macro_key, macro_value = operands
        if not is_variable_name(macro_key):
            raise NetQASMInstrError(f"{macro_key} is not a valid macro key")
        macro_keys.append(macro_key)
    if len(set(macro_keys)) < len(macro_keys):
        raise NetQASMInstrError(f"Macro keys need to be unique, not {macro_keys}")


def _assert_single_preamble_instr(list_of_operands, instr):
    if len(list_of_operands) != 1:
        raise NetQASMInstrError(f"Preamble should contain exactly one f{instr} instruction")


def _assert_single_preamble_arg(list_of_operands, instr):
    for operands in list_of_operands:
        if len(operands) != 1:
            raise NetQASMSyntaxError(f"Preamble instruction {instr} should contain exactly one argument, "
                                     f"not {len(operands)} as in '{operands}'")


def _assign_branch_labels(subroutine):
    """Finds assigns the branch labels in a subroutine (inplace)"""
    branch_labels = {}
    command_number = 0
    commands = subroutine.commands
    while command_number < len(commands):
        command = commands[command_number]
        if not isinstance(command, BranchLabel):
            command_number += 1
            continue
        branch_label = command.name
        if branch_label in branch_labels:
            raise NetQASMSyntaxError("branch labels need to be unique, name {branch_label} already used")
        # Assing the label to the line/command number
        branch_labels[branch_label] = Constant(command_number)
        # Remove the line
        commands = commands[:command_number] + commands[command_number + 1:]
    subroutine.commands = commands
    _update_labels(subroutine, branch_labels)


def _update_labels(subroutine, variables, from_command=0):
    """Updates labels in a subroutine with given values"""
    for command in subroutine.commands[from_command:]:
        if isinstance(command, Command):
            _update_labels_in_command(command, variables)


def _update_labels_in_command(command, variables):
    for i, operand in enumerate(command.operands):
        new_operand = _update_labels_in_operand(operand, variables)
        command.operands[i] = new_operand


def _update_labels_in_operand(operand, labels):
    if isinstance(operand, Label):
        for label, value in labels.items():
            if operand.name == label:
                return value
    return operand


def _get_unused_address(current_addresses):
    for address in count(0):
        if address not in current_addresses:
            return address


# def _find_current_branch_variables(subroutine: str):
#     """Finds the current branch variables in a subroutine (str) and returns these as a list"""
#     # NOTE preamble definitions are ignored
#     # NOTE there is no checking here for valid and unique variable names
#     preamble_lines, body_lines = _split_preamble_body(subroutine)

#     branch_variables = []
#     for line in body_lines:
#         # A line defining a branch variable should end with BRANCH_END
#         if line.endswith(Symbols.BRANCH_END):
#             branch_variables.append(line.rstrip(Symbols.BRANCH_END))

#         return branch_variables


def _make_args_operands(subroutine):
    for command in subroutine.commands:
        if not isinstance(command, Command):
            continue
        command.operands = command.args + command.operands
        command.args = []


_REPLACE_CONSTANTS_EXCEPTION = [
    (Instruction.SET, 1),
    (Instruction.JMP, 0),
    (Instruction.BEZ, 1),
    (Instruction.BNZ, 1),
    (Instruction.BEQ, 2),
    (Instruction.BNE, 2),
    (Instruction.BLT, 2),
    (Instruction.BGE, 2),
]


def _replace_constants(subroutine):
    current_registers = get_current_registers(subroutine)

    def reg_and_set_cmd(reg_i, value):
        register = Register(RegisterName.R, reg_i)
        if register in current_registers:
            raise RuntimeError("Could not replace constant since no registers left")
        set_command = Command(
            instruction=Instruction.SET,
            args=[],
            operands=[register, value],
        )

        return register, set_command

    i = 0
    while i < len(subroutine.commands):
        command = subroutine.commands[i]
        if not isinstance(command, Command):
            i += 1
            continue
        reg_i = 2 ** REG_INDEX_BITS - 1
        for j, operand in enumerate(command.operands):
            if isinstance(operand, Constant) and (command.instruction, j) not in _REPLACE_CONSTANTS_EXCEPTION:
                register, set_command = reg_and_set_cmd(reg_i, operand)
                subroutine.commands.insert(i, set_command)
                command.operands[j] = register

                reg_i -= 1
                i += 1
            else:
                if isinstance(operand, ArrayEntry):
                    attrs = ["index"]
                elif isinstance(operand, ArraySlice):
                    attrs = ["start", "stop"]
                else:
                    continue
                for attr in attrs:
                    value = getattr(operand, attr)
                    if isinstance(value, int):
                        value = Constant(value)
                    if isinstance(value, Constant):
                        register, set_command = reg_and_set_cmd(reg_i, value)
                        subroutine.commands.insert(i, set_command)
                        setattr(operand, attr, register)

                        reg_i -= 1
                        i += 1
        i += 1


# def _expand_slices(subroutine):
#     for command in subroutine.commands:
#         for operand in command.operands:
#             if isinstance(operand, ArraySlice):
#                 pass


def get_current_registers(subroutine):
    current_registers = []
    for command in subroutine.commands:
        if not isinstance(command, Command):
            continue
        if command.instruction == Instruction.SET:
            register = command.operands[0]
            if register not in current_registers:
                current_registers.append(register)
    return current_registers
