cd /workspace/litigation-classifier/batch2
until grep -q "HARVEST DONE" harvest.log 2>/dev/null; do python3 harvest.py >> harvest.log 2>&1 || sleep 60; done
until grep -q "LABEL DONE" label.log 2>/dev/null; do python3 label2.py >> label.log 2>&1 || sleep 60; done
until grep -q "RECAP DONE" recap.log 2>/dev/null; do python3 recap2.py >> recap.log 2>&1 || sleep 60; done
python3 finalize.py > finalize.log 2>&1; echo ALL DONE
