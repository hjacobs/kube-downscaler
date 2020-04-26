# Deploy Kube-downscaler using Helm chart

This directory contains tutorial to deploy Kube-downscaler and manage uptime of sample Flask applications in different time zones.

## Configuring your Deployment to downscale

Please add below annotations based on timezone your deployment should run:
```
metadata:
  annotations:
    downscaler/uptime: "Mon-Fri 07:00-19:00 US/Eastern"
```
Note: For more configuration details please, refer [here](https://github.com/hjacobs/kube-downscaler#configuration).

## Architecture
The diagram below depicts how a Kube-downscaler agent control applications.
![Alt text](images/architecture.png?raw=true "Kube Kube-downscaler diagram")

## Quick Start
Below are instructions to quickly install and configure Kube-downscaler.

### Installing Kube-downscaler

1. Make sure connected to right cluster:
```
kubectl config current-context
```
2. Set right environment depending on cluster:
```
export KDS_ENV='[minikube | testing | staging | production]'
```
3. Before deploy make sure to update *values.yaml* in Kube-downscaler chart depending on your cluster support for RBAC:
```
rbac:
  create: false
```
Note: In case RBAC is active new service account will be created for Kube-downscaler with certain privileges, otherwise 'default' one will be used.

4. Deploy Kube-downscaler:
```
helm install . --values "config/${KDS_ENV}.yaml" --namespace default  --name kube-downscaler
```

5. Check the deployed release status:
```
helm list
```
```
NAME            	REVISION	UPDATED                 	STATUS  	CHART                	APP VERSION	NAMESPACE
kube-downscaler      	1       	Tue Sep 25 02:07:58 2018	DEPLOYED	kube-downscaler-0.5.1	0.5.1      	default
```

6. Check Kube-downscaler pod is up and running:
```
kubectl get pods
```
```
NAME                                               READY     STATUS    RESTARTS   AGE
kube-downscaler-kube-downscaler-7f58c6b5b7-rnglz   1/1       Running   0          6m
```

7. Check Kubernetes event logs, to make sure of successful deployment of Kube-downscaler:
```
kubectl get events -w
```


### Deploying sample applications using Kube-downscaler
In this tutorial we will show how to deploy Kube-downscaler and test with sample Flask application.

1. Deploy Flask applications:
```
kubectl apply -f tutorial/flaskapp/flask_1.yaml
kubectl apply -f tutorial/flaskapp/flask_2.yaml
```

2. Ensure the following Kubernetes pods are up and running: flask-v1-tutorial-* , flask-v2-tutorial-* :
```
kubectl get pods
```
```
NAME                                 READY     STATUS    RESTARTS   AGE
flask-v1-tutorial-6b59556b55-kd2tv   1/1       Running   0          1m
flask-v2-tutorial-575fd64689-rkf55   1/1       Running   0          1m
```
Note: Deployments have grace period, which means Kube-downscaler will wait 15min to take any actions after pods get started.

3. Check Kube-downscaler pod logs:
```
kubectl logs -f kube-downscaler-55b9f8ffd8-5k9q4
```
```
2018-09-25 18:13:56,253 INFO: Deployment default/flask-v1-tutorial within grace period (900s), not scaling down (yet)
2018-09-25 18:13:56,253 INFO: Deployment default/flask-v2-tutorial within grace period (900s), not scaling down (yet)
2018-09-25 18:14:01,310 INFO: Scaling down Deployment default/flask-v1-tutorial from 1 to 0 replicas (uptime: Mon-FRI 07:00-19:00 US/Eastern, downtime: never)
2018-09-25 18:14:01,327 INFO: Scaling down Deployment default/flask-v2-tutorial from 1 to 0 replicas (uptime: Thu-Fri 07:00-19:00 US/Pacific, downtime: never)
```

### Uninstalling Sample Applications

1. To uninstall applications, run:
```
kubectl delete -f tutorial/flaskapp/flask_1.yaml
kubectl delete -f tutorial/flaskapp/flask_2.yaml
```

## Acknowledgments

Thanks to [Kube-downscaler](https://github.com/hjacobs/kube-downscaler) project authored by [Henning Jacobs](https://github.com/hjacobs).
