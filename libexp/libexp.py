from kubernetes import client


API = 'ml.intel.com'
API_VERSION = 'v1'
EXPERIMENT = "experiment"
EXPERIMENTS = "experiments"
RUN = "run"
RUNS = "runs"


# Simple Experiments API wrapper for kube client
class Client(object):
    def __init__(self, namespace='default'):
        self.namespace = namespace
        self.k8s = client.CustomObjectsApi()

    # Type Definitions

    def ensure_crds_exist(self):
        # TODO(CD)
        pass

    # Experiments

    def list_experiments(self):
        response = self.k8s.list_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                EXPERIMENTS)
        return [Experiment.from_body(item) for item in response['items']]

    def get_experiment(self, name):
        response = self.k8s.get_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                EXPERIMENTS,
                name)
        return Experiment.from_body(response)

    def create_experiment(self, exp):
        response = self.k8s.create_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                EXPERIMENTS,
                body=exp.to_body())
        return Experiment.from_body(response)

    def update_experiment(self, exp):
        response = self.k8s.replace_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                EXPERIMENTS,
                exp.name,
                exp.to_body())
        return Experiment.from_body(response)

    def delete_experiment(self, name):
        return self.k8s.delete_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                EXPERIMENTS,
                name,
                client.models.V1DeleteOptions())

    # Experiment Runs

    def list_runs(self):
        response = self.k8s.list_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                RUNS)
        return [Run.from_body(item) for item in response['items']]

    def get_run(self, name):
        response = self.k8s.get_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                RUNS,
                name)
        return Run.from_body(response)

    def create_run(self, run):
        response = self.k8s.create_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                RUNS,
                body=run.to_body())
        return Run.from_body(response)

    def update_run(self, run):
        response = self.k8s.replace_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                RUNS,
                run.name,
                run.to_body())
        return Run.from_body(response)

    def delete_run(self, name):
        return self.k8s.delete_namespaced_custom_object(
                API,
                API_VERSION,
                self.namespace,
                RUNS,
                name,
                client.models.V1DeleteOptions())


class Experiment(object):
    def __init__(self, name, job_template, status={}, meta={}):
        self.name = name
        self.job_template = job_template
        self.status = status
        self.meta = meta
        self.meta['name'] = self.name

    def uid(self):
        return self.meta.get('uid')

    def to_body(self):
        return {
            'apiVersion': "{}/{}".format(API, API_VERSION),
            'kind': EXPERIMENT.title(),
            'metadata': self.meta,
            'spec': {
                'jobSpec': self.job_template
            },
            'status': self.status
        }

    @staticmethod
    def from_body(body):
        return Experiment(body['metadata']['name'],
                          body.get('spec', {}).get('jobSpec'),
                          meta=body['metadata'],
                          status=body.get('status', {}))


class Run(object):
    def __init__(self, name, params, exp_name, exp_uid, status={}, meta={}):
        self.name = name
        self.params = params
        self.meta = meta
        self.status = status
        self.meta['name'] = self.name
        self.meta['ownerReferences'] = [
            {
                'apiVersion': '{}/{}'.format(API, API_VERSION),
                'controller': True,
                'kind': EXPERIMENT.title(),
                'name': exp_name,
                'uid': exp_uid
            }
        ]
        labels = self.meta.get('labels', {})
        labels['experiment'] = exp_name
        self.meta['labels'] = labels

    def results(self):
        return self.status.get('results', {})

    # extends `.status.results` with the supplied map
    def record_results(self, new_results):
        old_results = self.status.get('results', {})
        self.status['results'] = old_results
        old_results.update(new_results)

    def to_body(self):
        return {
            'apiVersion': "{}/{}".format(API, API_VERSION),
            'kind': RUN.title(),
            'metadata': self.meta,
            'spec': {
                'parameters': self.params
            },
            'status': self.status
        }

    @staticmethod
    def from_body(body):
        return Run(body['metadata']['name'],
                   body.get('spec', {}).get('parameters'),
                   body['metadata']['ownerReferences'][0]['name'],
                   body['metadata']['ownerReferences'][0]['uid'],
                   meta=body['metadata'],
                   status=body.get('status', {}))