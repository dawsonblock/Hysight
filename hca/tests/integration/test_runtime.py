from hca.runtime.runtime import Runtime


def test_run_completes():
    runtime = Runtime()
    run_id = runtime.run("echo greeting")
    assert isinstance(run_id, str)