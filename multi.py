#! python3.10

"""

This control different python processes with separate virtual envs.

being sufficiently ISO with K8 or compose interface allows the user to use those
solutions instead of the multi.py. (which should provide a much robust
scaling options than this.)

Thefor it is self-prohibited to implement any buisness logic in this and is
prefered to use the orchestrator to this intent (which is a standalone blade) 

"""

import shlex
import sys
import json
import argparse
import yaml
from multiprocessing import Process, current_process
import subprocess
import time
import os
import logging
from venv import EnvBuilder


# Configure logger for 'blade' with no propagation
logger = logging.getLogger('blade')
logger.propagate = False  # Stop this logger from propagating messages to the root logger
logger.setLevel(logging.DEBUG)  # Set the minimum log level


handler = logging.StreamHandler()



def ensure_virtualenv(venv_path):
    if not os.path.exists(venv_path):
        logger.info(f"Creating virtual environment at {venv_path}")
        builder = EnvBuilder(with_pip=True)
        builder.create(venv_path)
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
        if os.path.exists(requirements_path):
            subprocess.call([pip_path, 'install', '-r', requirements_path])
        else:
            logger.warning(f"requirements.txt not found at {requirements_path} - proceeding without installing packages.")
    else:
        logger.info(f"Virtual environment already exists at {venv_path}")

def run_blade_server(_config, topology, print_cmd, jlog):
    # If the print_cmd flag is set, print the command instead of executing
    blade_path = "blades/__init__.py"
    bare_cmd = [blade_path, "--topology", json.dumps(topology), "--blade", json.dumps(_config)]
    if jlog:
        bare_cmd.extend(['--jlog'])
    if print_cmd != '' and print_cmd == _config['name']:
        topology_arg = shlex.quote(json.dumps(topology))
        blade_arg = shlex.quote(json.dumps(_config))
        bare_cmd = [blade_path, "--topology", topology_arg, "--blade", blade_arg]
        print("{}".format(' '.join(bare_cmd))) # / ! \ meant to be a print
    if print_cmd != '':
        return  # Exit if you're only printing the command

    current_process().name = _config['name']  # Set the process name to the blade's name
    if not os.path.exists(blade_path):
        logger.error(f"'{blade_path}' does not exist in the current directory.")
        return

    venv_path = _config.get('venv')
    if not venv_path:
        logger.error(f"'venv' path not provided in configuration.")
        return

    ensure_virtualenv(venv_path)
    python_executable = os.path.join(venv_path, 'bin', 'python')
    cmd = [python_executable]
    cmd.extend(bare_cmd)

    while True:
        logger.info(f"Starting server {_config['name']}.")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)

        # Stream output
        with process.stdout:
            for line in iter(process.stdout.readline, ''):
                logger.info(line.strip())

        process.wait()
        logger.warning(f"Server {_config['name']} terminated with code {process.returncode}. Restarting...")
        time.sleep(1)

def load_config(filepath):
    try:
        with open(filepath, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"Cannot find configuration file at '{filepath}'.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        logger.error(f"Failed to parse YAML file '{filepath}'. Reason: {exc}")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Multiple server manager")
    parser.add_argument("-c", "--config", type=str, default="topology/standalone.yaml", help="Path to configuration YAML file")
    parser.add_argument("-cmd", "--print_cmd_only", type=str, default='', help="Print the commands and exits")
    parser.add_argument("--jlog", action="store_true", help="Format logs in JSON")
    args = parser.parse_args()
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    config = load_config(args.config)
    if not config or "blades" not in config:
        logger.error(f"Configuration file '{args.config}' is either empty or does not contain a 'blades' section.")
        sys.exit(1)

    processes = []
    for _config in config.get("blades", []):
        if _config.get("managed", False):
            p = Process(target=run_blade_server, args=(_config, config, args.print_cmd_only, args.jlog))
            p.start()
            processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Terminating processes.")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()

