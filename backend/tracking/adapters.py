"""Domain adapters preserve every original field; definitions are never guessed."""
class DeepLearningTracker:
    domain='deep_learning'
    def normalize(self,record,source):
        return {'domain':self.domain,'raw':record,'metrics':record.get('metrics',{}),'units':record.get('units',{}),'definitions':record.get('definitions',{}),'source':source,'association':'declared' if record.get('run_id') else 'pending_confirmation'}
class PoseEstimationTracker(DeepLearningTracker):domain='pose_estimation'
class ScientificSimulationTracker(DeepLearningTracker):domain='scientific_simulation'
