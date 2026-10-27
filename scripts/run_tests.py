import os, json, sys, time, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
OUTPUT=ROOT/os.getenv("AETHER_EVIDENCE_DIR","verification/final")
OUTPUT.mkdir(parents=True,exist_ok=True)
suite=unittest.defaultTestLoader.discover(str(ROOT/'backend/tests'))
start=time.monotonic()
with (OUTPUT/'unittest.log').open('w') as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
summary=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),elapsed_seconds=time.monotonic()-start)
(OUTPUT/'test_results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
sys.exit(not result.wasSuccessful())
