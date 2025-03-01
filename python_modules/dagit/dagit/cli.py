import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from typing import Optional

import click
from dagster import check
from dagster.cli.workspace import Workspace, get_workspace_from_kwargs, workspace_target_argument
from dagster.cli.workspace.cli_target import WORKSPACE_TARGET_WARNING
from dagster.core.instance import DagsterInstance, is_dagster_home_set
from dagster.core.telemetry import START_DAGIT_WEBSERVER, log_action
from dagster.utils import DEFAULT_WORKSPACE_YAML_FILENAME
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from .app import create_app_from_workspace
from .telemetry import upload_logs
from .version import __version__


def create_dagit_cli():
    return ui  # pylint: disable=no-value-for-parameter


DEFAULT_DAGIT_HOST = "127.0.0.1"
DEFAULT_DAGIT_PORT = 3000

DEFAULT_DB_STATEMENT_TIMEOUT = 5000  # 5 sec


@click.command(
    name="ui",
    help=(
        "Run dagit. Loads a repository or pipeline.\n\n{warning}".format(
            warning=WORKSPACE_TARGET_WARNING
        )
        + (
            "\n\nExamples:"
            "\n\n1. dagit (works if .{default_filename} exists)"
            "\n\n2. dagit -w path/to/{default_filename}"
            "\n\n3. dagit -f path/to/file.py"
            "\n\n4. dagit -f path/to/file.py -d path/to/working_directory"
            "\n\n5. dagit -m some_module"
            "\n\n6. dagit -f path/to/file.py -a define_repo"
            "\n\n7. dagit -m some_module -a define_repo"
            "\n\n8. dagit -p 3333"
            "\n\nOptions can also provide arguments via environment variables prefixed with DAGIT"
            "\n\nFor example, DAGIT_PORT=3333 dagit"
        ).format(default_filename=DEFAULT_WORKSPACE_YAML_FILENAME)
    ),
)
@workspace_target_argument
@click.option(
    "--host",
    "-h",
    type=click.STRING,
    default=DEFAULT_DAGIT_HOST,
    help="Host to run server on",
    show_default=True,
)
@click.option(
    "--port",
    "-p",
    type=click.INT,
    help="Port to run server on, default is {default_port}".format(default_port=DEFAULT_DAGIT_PORT),
)
@click.option(
    "--path-prefix",
    "-l",
    type=click.STRING,
    default="",
    help="The path prefix where Dagit will be hosted (eg: /dagit)",
    show_default=True,
)
@click.option(
    "--db-statement-timeout",
    help="The timeout in milliseconds to set on database statements sent "
    "to the DagsterInstance. Not respected in all configurations.",
    default=DEFAULT_DB_STATEMENT_TIMEOUT,
    type=click.INT,
    show_default=True,
)
@click.option(
    "--read-only",
    help="Start Dagit in read-only mode, where all mutations such as launching runs and "
    "turning schedules on/off are turned off.",
    is_flag=True,
)
@click.version_option(version=__version__, prog_name="dagit")
def ui(host, port, path_prefix, db_statement_timeout, read_only, **kwargs):
    # add the path for the cwd so imports in dynamically loaded code work correctly
    sys.path.append(os.getcwd())

    if port is None:
        port_lookup = True
        port = DEFAULT_DAGIT_PORT
    else:
        port_lookup = False

    host_dagit_ui(host, port, path_prefix, db_statement_timeout, port_lookup, read_only, **kwargs)


@contextmanager
def _get_instance():
    if is_dagster_home_set():
        with DagsterInstance.get() as instance:
            yield instance
    else:
        with tempfile.TemporaryDirectory() as tempdir:
            click.echo(
                f"Using temporary directory {tempdir} for storage. This will be removed when dagit exits.\n"
                "To persist information across sessions, set the environment variable DAGSTER_HOME to a directory to use.\n"
            )
            with DagsterInstance.local_temp(tempdir) as instance:
                yield instance


def host_dagit_ui(
    host, port, path_prefix, db_statement_timeout, port_lookup=True, read_only=False, **kwargs
):

    with _get_instance() as instance:
        # Allow the instance components to change behavior in the context of a long running server process
        instance.optimize_for_dagit(db_statement_timeout)

        with get_workspace_from_kwargs(kwargs) as workspace:
            if not workspace:
                raise Exception("Unable to load workspace with cli_args: {}".format(kwargs))

            host_dagit_ui_with_workspace(
                instance, workspace, host, port, path_prefix, port_lookup, read_only
            )


def host_dagit_ui_with_workspace(
    instance: DagsterInstance,
    workspace: Workspace,
    host: Optional[str],
    port: int,
    path_prefix: str,
    port_lookup: bool = True,
    read_only: bool = False,
):
    check.inst_param(instance, "instance", DagsterInstance)
    check.inst_param(workspace, "workspace", Workspace)
    check.opt_str_param(host, "host")
    check.int_param(port, "port")
    check.str_param(path_prefix, "path_prefix")
    check.bool_param(port_lookup, "port_lookup")
    check.bool_param(read_only, "read_only")

    app = create_app_from_workspace(workspace, instance, path_prefix, read_only)

    start_server(instance, host, port, path_prefix, app, port_lookup)


@contextmanager
def uploading_logging_thread():
    stop_event = threading.Event()
    logging_thread = threading.Thread(
        target=upload_logs, args=([stop_event]), name="telemetry-upload"
    )
    try:
        logging_thread.start()
        yield
    finally:
        stop_event.set()
        logging_thread.join()


def start_server(instance, host, port, path_prefix, app, port_lookup, port_lookup_attempts=0):
    server = pywsgi.WSGIServer((host, port), app, handler_class=WebSocketHandler)

    click.echo(
        "Serving on http://{host}:{port}{path_prefix} in process {pid}".format(
            host=host, port=port, path_prefix=path_prefix, pid=os.getpid()
        )
    )

    log_action(instance, START_DAGIT_WEBSERVER)
    with uploading_logging_thread():
        try:
            server.serve_forever()
        except OSError as os_error:
            if "Address already in use" in str(os_error):
                if port_lookup and (
                    port_lookup_attempts > 0
                    or click.confirm(
                        (
                            "Another process on your machine is already listening on port {port}. "
                            "Would you like to run the app at another port instead?"
                        ).format(port=port)
                    )
                ):
                    port_lookup_attempts += 1
                    start_server(
                        instance,
                        host,
                        port + port_lookup_attempts,
                        path_prefix,
                        app,
                        True,
                        port_lookup_attempts,
                    )
                else:
                    raise Exception(
                        f"Another process on your machine is already listening on port {port}. "
                        "It is possible that you have another instance of dagit "
                        "running somewhere using the same port. Or it could be another "
                        "random process. Either kill that process or use the -p option to "
                        "select another port."
                    ) from os_error
            else:
                raise os_error


cli = create_dagit_cli()


def main():
    # click magic
    cli(auto_envvar_prefix="DAGIT")  # pylint:disable=E1120
