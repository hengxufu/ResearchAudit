import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pathlib import Path
import tempfile
from backend import storage
from backend.v2.reporting import pdf
old=storage.DB
with tempfile.TemporaryDirectory(dir='.',prefix='.test-runs-pdf-') as tmp:
    storage.DB=Path(tmp)
    value={'root':'TEST DATA / 科研测试','runs':[{'id':'TEST','name':'TEST 温度场验证','params':{},'metrics':{'temperature_error_K':.125,'relative_energy_residual':.00001},'series':{},'sources':[{'path':'TEST_DATA/temperature.csv','sha256':'a'*64,'bytes':100}]}],'evidence':[],'issues':[],'git':{'commit':None,'status':None}}
    id=storage.save(value['root'],value)
    Path('output/pdf/TEST_DATA-v2-report.pdf').write_bytes(pdf(id))
storage.DB=old
