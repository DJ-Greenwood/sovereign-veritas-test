"""G1: model_action.server_devices reads the llama-server log; it never guesses."""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("model_action_g1", os.path.join(HERE, "..", "tools", "model_action.py"))
ma = importlib.util.module_from_spec(spec)
sys.modules["model_action_g1"] = ma
spec.loader.exec_module(ma)


def test_no_log_is_not_recorded():
    assert ma.server_devices(None) == "not recorded"


def test_missing_log_is_unreadable(tmp_path):
    assert ma.server_devices(str(tmp_path / "nope.log")).startswith("not recorded")


def test_gpu_lines_are_found(tmp_path):
    p = tmp_path / "server.log"
    p.write_text("ggml_opencl: device: 'QUALCOMM Adreno(TM) 830'\nload_tensors: offloaded 29/29 layers to GPU\n")
    out = ma.server_devices(str(p))
    assert "Adreno" in out and "29/29" in out


def test_cpu_only_log(tmp_path):
    p = tmp_path / "server.log"
    p.write_text("main: server is listening on http://127.0.0.1:8080\n")
    assert ma.server_devices(str(p)).startswith("CPU")
