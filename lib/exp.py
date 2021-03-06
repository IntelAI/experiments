from kubernetes import client
from collections import namedtuple
import copy
import json
import logging
import os
import time
import uuid
import yaml


API = 'ml.intel.com'
API_VERSION = 'v1'
EXPERIMENT = "experiment"
EXPERIMENTS = "experiments"
RESULT = "result"
RESULTS = "results"

LOG = logging.getLogger(__name__)


def deserialize_object(serialized_bytes, class_name):
    # Necessary to get access to request body deserialization methods.
    api_client = client.ApiClient()
    Response = namedtuple('Response', ['data'])
    body = Response(serialized_bytes)
    return api_client.deserialize(body, class_name)


# Simple Experiments API wrapper for kube client
class Client(object):
    def __init__(self, namespace='default'):
        self.namespace = namespace
        self.k8s = client.CustomObjectsApi()
        self.batch = client.BatchV1Api()

    def _retry_poll_api(self, api, max_retries_error, max_retries=30,
                        retry_interval=1, api_kwargs={}):
        """
        Helper function that has a polling loop to retry calling the specified
        API until it's successful (the client does not throw an Api Exception).

        :param api: Kubernetes Client API function to call.
        :param max_retries_error: Error message to print if the maximum retries
                                  has been reached and the API call still fails
        :param max_retries: Maximum number of times to retry calling the API
        :param retry_interval: Number of seconds to wait between API retries
        :param api_kwargs: Dictionary of arguments to pass to the Kubernetes
        Client API function.
        :return: Return value of the client API call
        """

        if not callable(api):
            raise TypeError("Invalid 'api' parameter type.  Must be a callable"
                            " function.")

        retry_count = 0
        while retry_count < max_retries:
            try:
                return api(**api_kwargs)
            except client.rest.ApiException:
                time.sleep(retry_interval)
                retry_count += 1

                if retry_count >= max_retries:
                    # If we've exceeded the retry count, then raise the
                    # original exception
                    LOG.error(max_retries_error)
                    raise
                else:
                    LOG.debug("Retrying {}/{} \r".format(retry_count,
                                                         max_retries))

    # Type Definitions

    def create_crds(self):
        # API Extensions V1 beta1 API client.
        crd_api = client.ApiextensionsV1beta1Api()

        crd_dir = os.path.join(os.path.dirname(__file__), '../resources/crds')
        crd_paths = [os.path.abspath(os.path.join(crd_dir, name))
                     for name in os.listdir(crd_dir)]

        for path in crd_paths:
            with open(path) as crd_file:
                crd_json = json.dumps(
                    yaml.load(crd_file.read()), sort_keys=True, indent=2)
                crd = deserialize_object(
                    crd_json, 'V1beta1CustomResourceDefinition')
                try:
                    crd_api.create_custom_resource_definition(crd)
                except Exception:
                    pass

    # Experiments

    def current_experiment(self):
        exp_name = os.getenv('EXPERIMENT_NAME')
        if not exp_name:
            raise Exception('Environment variable EXPERIMENT_NAME not set')
        return self.get_experiment(exp_name)

    def list_experiments(self):
        max_retries_error = ("Maximum retries reached when getting list of "
                             "experiments in namespace {}.".format(
                              self.namespace))
        response = self._retry_poll_api(
            self.k8s.list_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": EXPERIMENTS
            })

        return [Experiment.from_body(item) for item in response['items']]

    def get_experiment(self, name):
        max_retries_error = ("Maximum retries reached when checking for "
                             "experiment {} in namespace {}.".format(
                              name, self.namespace))
        response = self._retry_poll_api(
            self.k8s.get_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": EXPERIMENTS,
                "name": name
            })
        return Experiment.from_body(response)

    def create_experiment(self, exp):
        max_retries_error = ("Maximum retries reached when creating experiment"
                             " in namespace {}.".format(self.namespace))
        response = self._retry_poll_api(
            self.k8s.create_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": EXPERIMENTS,
                "body": exp.to_body()
            })
        return Experiment.from_body(response)

    def update_experiment(self, exp):
        max_retries_error = ("Maximum retries reached when updating experiment"
                             " {} in namespace {}.".format(
                              exp.name, self.namespace))
        response = self._retry_poll_api(
            self.k8s.replace_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": EXPERIMENTS,
                "name": exp.name,
                "body": exp.to_body()
            })
        return Experiment.from_body(response)

    def delete_experiment(self, name):
        max_retries_error = ("Maximum retries reached when deleting experiment"
                             " {} in namespace {}.".format(
                              name, self.namespace))
        return self._retry_poll_api(
            self.k8s.delete_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": EXPERIMENTS,
                "name": name,
                "body": client.models.V1DeleteOptions()
            })

    # Experiment Results

    def list_results(self):
        max_retries_error = ("Maximum retries reached when listing results "
                             "in namespace {}.".format(self.namespace))
        response = self._retry_poll_api(
            self.k8s.list_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": RESULTS
            })
        return [Result.from_body(item) for item in response['items']]

    def get_result(self, name):
        max_retries_error = ("Maximum retries reached when checking for "
                             "result {} in namespace {}.".format(
                              name, self.namespace))
        response = self._retry_poll_api(
            self.k8s.get_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": RESULTS,
                "name": name
            })
        return Result.from_body(response)

    def create_result(self, result):
        max_retries_error = ("Maximum retries reached when creating result "
                             "in namespace {}.".format(self.namespace))
        response = self._retry_poll_api(
            self.k8s.create_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": RESULTS,
                "body": result.to_body()
            })
        return Result.from_body(response)

    def update_result(self, result):
        max_retries_error = ("Maximum retries reached when updating result {} "
                             "in namespace {}.".format(
                              result.name, self.namespace))
        response = self._retry_poll_api(
            self.k8s.replace_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": RESULTS,
                "name": result.name,
                "body": result.to_body()
            })

        return Result.from_body(response)

    def delete_result(self, name):
        max_retries_error = ("Maximum retries reached when deleting result {} "
                             "in namespace {}.".format(
                              name, self.namespace))
        return self._retry_poll_api(
            self.k8s.delete_namespaced_custom_object, max_retries_error,
            api_kwargs={
                "group": API,
                "version": API_VERSION,
                "namespace": self.namespace,
                "plural": RESULTS,
                "name": name,
                "body": client.models.V1DeleteOptions()
            })

    def list_jobs(self, experiment):
        max_retries_error = ("Maximum retries reached when listing jobs in "
                             "namespace {}.".format(
                              self.namespace))
        return self._retry_poll_api(
            self.batch.list_namespaced_job, max_retries_error,
            api_kwargs={
                "namespace": self.namespace,
                "label_selector": 'experiment_uid={}'.format(experiment.uid())
            }).items

    def get_job(self, job_name):
        max_retries_error = ("Maximum retries reached when checking for "
                             "job {} in namespace {}.".format(
                              job_name, self.namespace))
        return self._retry_poll_api(
            self.batch.read_namespaced_job, max_retries_error,
            api_kwargs={
                "name": job_name,
                "namespace": self.namespace
            })

    def create_job(self, experiment, parameters):
        short_uuid = str(uuid.uuid4())[:8]
        metadata = {
            'name': "{}-{}".format(experiment.name, short_uuid),
            'labels': {
                'experiment_uid': experiment.uid(),
                'experiment_name': experiment.name
            },
            'annotations': {
                'job_parameters': json.dumps(parameters)
            },
            'ownerReferences': [
                {
                    'apiVersion': '{}/{}'.format(API, API_VERSION),
                    'controller': True,
                    'kind': EXPERIMENT.title(),
                    'name': experiment.name,
                    'uid': experiment.uid(),
                    'blockOwnerDeletion': True
                }
            ]
        }
        job_name = metadata['name']

        template = copy.deepcopy(experiment.job_template)

        containers = None
        if 'template' in template and \
           'spec' in template['template'] and \
           'containers' in template['template']['spec']:

            containers = template['template']['spec']['containers']

        if not containers:
            raise Exception(
                "Container templates are not available in experiment job")

        experiment_environment_metadata = [
            {'name': 'JOB_NAME', 'value': job_name},
            {'name': 'EXPERIMENT_NAMESPACE', 'value': self.namespace},
            {'name': 'EXPERIMENT_NAME', 'value': experiment.name},
            {'name': 'EXPERIMENT_UID', 'value': experiment.uid()}
        ]

        # Provide parameters in environment variables, encoded like:
        # PARAMETER_X_FLOAT = "3.14"
        for parameter in parameters:
            value = parameters[parameter]
            value_kind = str(type(value).__name__)
            key = "PARAMETER_{}_{}".format(parameter, value_kind).upper()

            # To avoid python'ist boolean values.
            # Encode them as either 'true' or 'false'
            if value_kind == "bool":
                value = str(value).lower()

            experiment_environment_metadata.append(
                    {'name': key, 'value': str(value)})

        for container in containers:
            if not container.get('env'):
                container['env'] = []

            container['env'].extend(experiment_environment_metadata)

        job = client.models.V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=metadata,
            spec=deserialize_object(json.dumps(template), 'V1JobSpec'))

        max_retries_error = ("Maximum retries reached when creating job {} in "
                             "namespace {}.".format(
                              job_name, self.namespace))
        return self._retry_poll_api(
            self.batch.create_namespaced_job, max_retries_error,
            api_kwargs={
                "namespace": self.namespace,
                "body": job
            })


class Experiment(object):
    def __init__(self,
                 name,
                 job_template,
                 parameters=None,
                 status=None,
                 meta=None):
        if not parameters:
            parameters = {}
        if not status:
            status = {}
        if not meta:
            meta = {}
        self.name = name
        self.job_template = job_template
        self.parameters = parameters
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
                'jobSpec': self.job_template,
                'parameters': self.parameters
            },
            'status': self.status
        }

    def result(self, job):
        status = {}

        if not isinstance(job, client.models.V1Job):
            raise TypeError("job parameter must be a V1Job object.")

        if 'job_parameters' in job.metadata.annotations:
            status['job_parameters'] = json.loads(
                job.metadata.annotations['job_parameters'])

        return Result(
            job.metadata.name,
            self.name,
            self.uid(),
            status=status
        )

    @staticmethod
    def from_body(body):
        return Experiment(body['metadata']['name'],
                          body.get('spec', {}).get('jobSpec'),
                          body.get('spec', {}).get('parameters'),
                          meta=body['metadata'],
                          status=body.get('status', {}))


class Result(object):
    def __init__(self, name, exp_name, exp_uid, status=None, meta=None):
        if not status:
            status = {}
        if not meta:
            meta = {}

        self.name = name
        self.meta = meta
        self.status = status
        self.meta['name'] = self.name
        self.meta['ownerReferences'] = [
            {
                'apiVersion': '{}/{}'.format(API, API_VERSION),
                'controller': True,
                'kind': EXPERIMENT.title(),
                'name': exp_name,
                'uid': exp_uid,
                'blockOwnerDeletion': True
            }
        ]
        labels = self.meta.get('labels', {})
        labels['experiment'] = exp_name
        self.meta['labels'] = labels

    def values(self):
        return self.status.get('values', {})

    def job_parameters(self):
        return self.status.get('job_parameters', {})

    # extends `.status.values` with the supplied map
    def record_values(self, new_values):
        old_values = self.status.get('values', {})
        self.status['values'] = old_values
        old_values.update(new_values)

    def to_body(self):
        return {
            'apiVersion': "{}/{}".format(API, API_VERSION),
            'kind': RESULT.title(),
            'metadata': self.meta,
            'status': self.status
        }

    @staticmethod
    def from_body(body):
        return Result(body['metadata']['name'],
                      body['metadata']['ownerReferences'][0]['name'],
                      body['metadata']['ownerReferences'][0]['uid'],
                      meta=body['metadata'],
                      status=body.get('status', {}))
