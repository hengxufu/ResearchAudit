"""Real TensorBoard protobuf and MLflow file format TEST DATA."""
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary
from backend.collect import scan

def test_tensorboard_real_format(tmp_path):
    root=tmp_path/'TEST_DATA_TENSORBOARD';root.mkdir()
    writer=EventFileWriter(str(root))
    for step,val in [(0,3.0),(4,1.5)]:
        writer.add_event(Event(wall_time=step+1,step=step,summary=Summary(value=[Summary.Value(tag='loss',simple_value=val)])))
    writer.close()
    result=scan(root);r=result['runs'][0]
    assert r['series']['loss']==[3,1.5]
    assert r['series']['loss/step']==[0,4]
    assert r['metrics']['loss']==1.5
    assert not result['issues']

def test_mlflow_real_format(tmp_path):
    root=tmp_path/'TEST_DATA_MLFLOW';d=root/'run'/'metrics';d.mkdir(parents=True)
    (d/'loss').write_text('1000 3.0 0\n2000 1.5 4\n')
    result=scan(root)
    assert result['runs'][0]['series']['loss']==[3,1.5]
    assert result['runs'][0]['metrics']['loss']==1.5
    assert result['runs'][0]['sources'][0]['sha256']
