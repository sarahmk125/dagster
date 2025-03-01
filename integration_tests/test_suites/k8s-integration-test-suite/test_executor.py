import os

import pytest
from dagster import check
from dagster.core.storage.tags import DOCKER_IMAGE_TAG
from dagster.core.test_utils import create_run_for_test
from dagster.utils import load_yaml_from_path, merge_dicts
from dagster_k8s.client import DagsterKubernetesClient
from dagster_k8s.launcher import K8sRunLauncher
from dagster_k8s.test import wait_for_job_and_get_raw_logs
from dagster_k8s_test_infra.helm import TEST_AWS_CONFIGMAP_NAME
from dagster_k8s_test_infra.integration_utils import image_pull_policy
from dagster_test.test_project import (
    IS_BUILDKITE,
    ReOriginatedExternalPipelineForTest,
    get_test_project_docker_image,
    get_test_project_environments_path,
    get_test_project_location_and_external_pipeline,
)


@pytest.mark.integration
def test_k8s_run_launcher_default(
    dagster_instance_for_k8s_run_launcher, helm_namespace_for_k8s_run_launcher, dagster_docker_image
):
    # sanity check that we have a K8sRunLauncher
    check.inst(dagster_instance_for_k8s_run_launcher.run_launcher, K8sRunLauncher)
    pods = DagsterKubernetesClient.production_client().core_api.list_namespaced_pod(
        namespace=helm_namespace_for_k8s_run_launcher
    )
    celery_pod_names = [p.metadata.name for p in pods.items if "celery-workers" in p.metadata.name]
    check.invariant(not celery_pod_names)

    run_config = merge_dicts(
        load_yaml_from_path(os.path.join(get_test_project_environments_path(), "env.yaml")),
        load_yaml_from_path(os.path.join(get_test_project_environments_path(), "env_s3.yaml")),
        {
            "execution": {
                "k8s": {
                    "config": {
                        "job_namespace": helm_namespace_for_k8s_run_launcher,
                        "job_image": dagster_docker_image,
                        "image_pull_policy": image_pull_policy(),
                        "env_config_maps": ["dagster-pipeline-env"]
                        + ([TEST_AWS_CONFIGMAP_NAME] if not IS_BUILDKITE else []),
                    }
                }
            },
        },
    )

    pipeline_name = "demo_k8s_executor_pipeline"
    tags = {"key": "value"}

    with get_test_project_location_and_external_pipeline(pipeline_name) as (
        location,
        external_pipeline,
    ):
        run = create_run_for_test(
            dagster_instance_for_k8s_run_launcher,
            pipeline_name=pipeline_name,
            run_config=run_config,
            tags=tags,
            mode="default",
            pipeline_snapshot=external_pipeline.pipeline_snapshot,
            execution_plan_snapshot=location.get_external_execution_plan(
                external_pipeline, run_config, "default", None, None
            ).execution_plan_snapshot,
        )
        dagster_instance_for_k8s_run_launcher.launch_run(
            run.run_id,
            ReOriginatedExternalPipelineForTest(external_pipeline),
        )

        result = wait_for_job_and_get_raw_logs(
            job_name="dagster-run-%s" % run.run_id, namespace=helm_namespace_for_k8s_run_launcher
        )

        assert "PIPELINE_SUCCESS" in result, "no match, result: {}".format(result)

        updated_run = dagster_instance_for_k8s_run_launcher.get_run_by_id(run.run_id)
        assert updated_run.tags[DOCKER_IMAGE_TAG] == get_test_project_docker_image()


@pytest.mark.integration
def test_k8s_run_launcher_image_from_origin(
    dagster_instance_for_k8s_run_launcher, helm_namespace_for_k8s_run_launcher, dagster_docker_image
):
    # Like the previous test, but the executor doesn't supply an image - it's pulled
    # from the origin (see get_test_project_location_and_external_pipeline below) instead

    check.inst(dagster_instance_for_k8s_run_launcher.run_launcher, K8sRunLauncher)
    pods = DagsterKubernetesClient.production_client().core_api.list_namespaced_pod(
        namespace=helm_namespace_for_k8s_run_launcher
    )
    celery_pod_names = [p.metadata.name for p in pods.items if "celery-workers" in p.metadata.name]
    check.invariant(not celery_pod_names)

    run_config = merge_dicts(
        load_yaml_from_path(os.path.join(get_test_project_environments_path(), "env.yaml")),
        load_yaml_from_path(os.path.join(get_test_project_environments_path(), "env_s3.yaml")),
        {
            "execution": {
                "k8s": {
                    "config": {
                        "job_namespace": helm_namespace_for_k8s_run_launcher,
                        "image_pull_policy": image_pull_policy(),
                        "env_config_maps": ["dagster-pipeline-env"]
                        + ([TEST_AWS_CONFIGMAP_NAME] if not IS_BUILDKITE else []),
                    }
                }
            },
        },
    )

    pipeline_name = "demo_k8s_executor_pipeline"
    tags = {"key": "value"}

    with get_test_project_location_and_external_pipeline(pipeline_name, dagster_docker_image) as (
        location,
        external_pipeline,
    ):
        run = create_run_for_test(
            dagster_instance_for_k8s_run_launcher,
            pipeline_name=pipeline_name,
            run_config=run_config,
            tags=tags,
            mode="default",
            pipeline_snapshot=external_pipeline.pipeline_snapshot,
            execution_plan_snapshot=location.get_external_execution_plan(
                external_pipeline, run_config, "default", None, None
            ).execution_plan_snapshot,
        )
        dagster_instance_for_k8s_run_launcher.launch_run(
            run.run_id,
            ReOriginatedExternalPipelineForTest(
                external_pipeline, container_image=dagster_docker_image
            ),
        )

        result = wait_for_job_and_get_raw_logs(
            job_name="dagster-run-%s" % run.run_id, namespace=helm_namespace_for_k8s_run_launcher
        )

        assert "PIPELINE_SUCCESS" in result, "no match, result: {}".format(result)

        updated_run = dagster_instance_for_k8s_run_launcher.get_run_by_id(run.run_id)
        assert updated_run.tags[DOCKER_IMAGE_TAG] == get_test_project_docker_image()
