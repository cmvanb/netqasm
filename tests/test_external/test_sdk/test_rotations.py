from netqasm.sdk import Qubit
from netqasm.sdk.external import NetQASMConnection, simulate_application
from netqasm.runtime.application import default_app_instance
from netqasm.logging.glob import get_netqasm_logger

logger = get_netqasm_logger()


def run_alice():
    with NetQASMConnection("Alice") as alice:
        count = 0
        num = 10
        for _ in range(num):
            q = Qubit(alice)
            q.rot_X(n=1, d=1)  # pi / 2
            q.rot_X(n=2, d=2)  # 2 pi / 4
            q.rot_Y(n=1, d=1)  # pi / 2
            q.rot_Y(n=2, d=2)  # 2 pi / 4
            m = q.measure()
            alice.flush()
            count += m
        logger.info(count)
        assert count == 0


def test_rotations():
    app_instance = default_app_instance([
        ("Alice", run_alice),
    ])
    simulate_application(app_instance, use_app_config=False, enable_logging=False)
