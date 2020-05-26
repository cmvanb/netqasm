def create_ghz(down_epr_socket=None, up_epr_socket=None):
    r"""Local protocol to create a GHZ state between mutliples nodes.

    EPR pairs are generated in a line and turned into a GHZ state by performing half of a Bell measurement.
    That is, CNOT and H are applied but only the control qubit is measured.
    This measurement outcome is returned along with the qubit to be able to know what corrections might
    need to be applied.
    If the node is at the start or end of the line, the measurement outcome 0 is always returned since there
    is no measurement performed.
    The measurement outcome indicates if the next node in the line should flip its qubit to get the standard
    GHZ state: :math:`|0\rangle^{\otimes n} + |1\rangle^{\otimes n}`.

    Depending on if down_epr_socket and/or up_epr_socket is specified the node,
    either takes the role of the:
    * "start", which intialises the process and creates an EPR
      with the next node using the `up_epr_socket`.
    * "middle", which receives an EPR pair on the `down_epr_socket` and then
      creates one on the `up_epr_socket`.
    * "end", which receives an EPR pair on the `down_epr_socket`.
    NOTE There has to be exactly one "start" and exactly one "end" but zero or more "middle".
    NOTE Both `down_epr_socket` and `up_epr_socket` cannot be `None`.

    Parameters
    ----------
    down_epr_socket : :class:`.sdk.epr_socket.EPRSocket`
        The EPRSocket to be used for receiving EPR pairs from downstream.
    up_epr_socket : :class:`.sdk.epr_socket.EPRSocket`
        The EPRSocket to be used for create EPR pairs upstream.

    Returns
    -------
    tuple
        Of the form `(q, m)` where `q` is the qubit part of the state and `m` is the measurement outcome.
    """
    if down_epr_socket is None and up_epr_socket is None:
        raise TypeError("Both down_epr_socket and up_epr_socket cannot be None")

    if down_epr_socket is None:
        # Start role
        q = up_epr_socket.create()[0]
        return q, 0

    q_down = down_epr_socket.recv()[0]
    if up_epr_socket is None:
        # End role
        return q_down, 0

    # Middle role
    q_up = up_epr_socket.create()[0]
    # merge the states by doing half a Bell measurement
    q_down.cnot(q_up)
    m = q_up.measure()

    return q_down, m
