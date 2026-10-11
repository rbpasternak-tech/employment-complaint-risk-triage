cd /workspace/litigation-classifier
while pgrep -f "python3 sample.py" >/dev/null; do sleep 20; done
[ -s cases/index.json ] || { echo "sample failed"; exit 1; }
python3 label.py > label.log 2>&1; python3 recap.py > recap.log 2>&1; python3 analyze.py > analyze.log 2>&1; echo PIPELINE DONE
