import {spawn} from 'node:child_process';
const python=process.platform==='win32'?'backend/.venv/Scripts/python':'backend/.venv/bin/python';
const child=spawn(python,['-m','pytest','backend/tests/test_browser_audit.py','-q','--ds=config.postgres_test_settings'],{stdio:'inherit',env:{...process.env,RUN_BROWSER_AUDIT:'1'}});
child.on('error',()=>{console.error('Could not start the backend virtual environment.');process.exitCode=1});
child.on('exit',code=>{process.exitCode=code??1});
