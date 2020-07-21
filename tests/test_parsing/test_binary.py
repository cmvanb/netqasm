from netqasm.parsing import parse_text_subroutine, parse_binary_subroutine

from netqasm.instructions.vanilla import CphaseInstruction


def test():
    subroutine = """
# NETQASM 0.0
# APPID 0
# DEFINE ms @0

// Setup classical registers
set Q0 0
array 10 ms!
set R0 0

// Loop entry
LOOP:
beq R0 10 EXIT

// Loop body
qalloc Q0
init Q0
h Q0
meas Q0 M0

// Store to array
store M0 ms![R0]

qfree Q0
add R0 R0 1

// Loop exit
beq 0 0 LOOP
EXIT:
ret_reg M0
    """

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    data = bytes(subroutine)
    print(data)

    parsed_subroutine = parse_binary_subroutine(data)
    print(parsed_subroutine)

    for command, parsed_command in zip(subroutine.commands, parsed_subroutine.commands):
        print()
        print(repr(command))
        print(repr(parsed_command))
        assert command == parsed_command

    assert subroutine == parsed_subroutine


def test_rotations():
    subroutine = """
# NETQASM 0.0
# APPID 0

set Q0 0
qalloc Q0
init Q0

// Perform rotations
rot_x Q0 1 1  // rotate by 1 * pi / 1 = pi
rot_x Q0 1 4  // rotate by 1 * pi / 4 = pi / 4
rot_y Q0 7 22  // rotate by 7 pi / 22

qfree Q0
"""

    subroutine = parse_text_subroutine(subroutine)
    print(subroutine)
    data = bytes(subroutine)
    print(f"binary subroutine: {data}")

    parsed_subroutine = parse_binary_subroutine(data)
    print(parsed_subroutine)

    for command, parsed_command in zip(subroutine.commands, parsed_subroutine.commands):
        print(f"command: {command}, parsed_command: {parsed_command}")
        assert command == parsed_command

    assert subroutine == parsed_subroutine


def test_deserialize_subroutine():
    metadata = b"\x00\x00\x00\x00"
    cphase_gate = b"\x1F\x00\x00\x00\x00\x00\x00"
    raw = bytes(metadata + cphase_gate)
    print(raw)
    subroutine = parse_binary_subroutine(raw)
    print(subroutine)
    for instr in subroutine.commands:
        if isinstance(instr, CphaseInstruction):
            print(f"qreg0: {instr.qreg0}, qreg1: {instr.qreg1}")

    subroutine2 = parse_binary_subroutine(raw)
    print(subroutine2)


if __name__ == '__main__':
    test()
    test_rotations()
    test_deserialize_subroutine()
