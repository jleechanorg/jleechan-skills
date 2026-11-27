"""Harbor job hook binding the live inference sidecar before Codex auth upload."""

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import UUID


SIDECAR = 'harbor-docker-egress-control-sidecar'
RECEIPT = 'access-egress.json'
BINDING = '/run/harbor-access-binding.json'
PLUGIN = 'harbor_codex_egress:BindInferenceSidecar'
INFERENCE_HOST = 'chatgpt.com'
POLICY_HEADER = ['mode: controlled egress', 'allowlist: /opt/egress-sidecar/allowlist.txt']
OFFLINE_POLICY = [*POLICY_HEADER, '(empty: deny all controlled TCP egress)']
INSPECT = ('[{{json .Id}},{{json .Image}},{{json .State.Running}},{{json .HostConfig.NetworkMode}},'
           '{{json (index .Config.Labels "com.docker.compose.service")}},'
           '{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},{{json .Mounts}}]')


def plugin_cli_args(plugin, **kwargs):
    argv = ['--plugin', plugin]
    for name, value in kwargs.items():
        argv.extend(('--plugin-kwarg', f'{name}={json.dumps(value)}'))
    return argv


def docker_lines(*args):
    if os.environ.get('DOCKER_HOST') != 'unix:///var/run/docker.sock' or os.environ['PATH'] != os.defpath:
        raise ValueError('unexpected Docker context in inference guard')
    env = {key: os.environ[key] for key in ('DOCKER_HOST', 'HOME', 'PATH')}
    try:
        result = subprocess.run(['docker', *args], env=env, capture_output=True, text=True,
                                timeout=18, check=True)
        return result.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        raise ValueError('could not inspect live inference containers') from None


def bound_inference_containers(project, agent_image, egress_image, trial, *, qualify_route=None):
    listed = docker_lines('ps', '-aq', '--no-trunc', '--filter', f'label=com.docker.compose.project={project}')
    if len(set(listed)) != 2 or len(listed) != 2 or not all(re.fullmatch('[a-f0-9]{64}', item) for item in listed):
        raise ValueError('expected exactly two live inference container identities')
    rows = [json.loads(line) for line in docker_lines('inspect', '--type', 'container', '--format', INSPECT, *listed)]
    if len(rows) != 2 or not all(isinstance(row, list) and len(row) == 7 for row in rows):
        raise ValueError('incomplete live inference container inspection')
    if {row[0] for row in rows} != set(listed) or {row[4] for row in rows} != {'main', SIDECAR}:
        raise ValueError('unexpected live inference container identities')
    by_service = {row[4]: row for row in rows}
    main, sidecar = by_service['main'], by_service[SIDECAR]
    if (main[1] != agent_image or sidecar[1] != egress_image or main[2] is not True or sidecar[2] is not True
            or main[3] != f'container:{sidecar[0]}' or sidecar[3] != f'{project}_default' or sidecar[5] != 'healthy'):
        raise ValueError('running inference image, network namespace or health did not match qualification')
    if (sidecar[6] or any(mount.get('Type') != 'bind' or not Path(mount.get('Source', '')).is_absolute()
                         or not Path(mount['Source']).resolve().is_relative_to(trial.resolve())
                         for mount in (main[6] or []))):
        raise ValueError('inference containers have unexpected persistent or external mounts')
    command = ('exec', sidecar[0], 'network-policy')
    if docker_lines(*command, 'show') != OFFLINE_POLICY:
        raise ValueError('inference sidecar did not start in the qualified offline policy')
    if qualify_route is not None:
        qualify_route(project, main[0], sidecar[0])
    docker_lines(*command, 'allow', INFERENCE_HOST)
    observed = docker_lines(*command, 'show')
    if observed[:2] != POLICY_HEADER or len(observed) != 3 or observed[2].split() != ['1', INFERENCE_HOST]:
        raise ValueError('live inference network policy did not match qualification')
    docker_lines('exec', '--user', 'baseline', main[0], '/usr/local/bin/codex', '--harbor-check-preupload-route')
    return {'project': project, 'main': main[0], 'sidecar': sidecar[0], 'allowed_host': INFERENCE_HOST}


class BindInferenceSidecar:
    def __init__(self, *, egress_image, agent_image, scope, run_sha256):
        if not (re.fullmatch(r'codex-[a-f0-9]{24}__', scope)
                and re.fullmatch(r'[a-f0-9]{64}', run_sha256)
                and all(re.fullmatch(r'sha256:[a-f0-9]{64}', item) for item in (agent_image, egress_image))):
            raise ValueError('invalid qualified Docker binding')
        self.scope = scope
        self.egress_image = egress_image
        self.agent_image = agent_image
        self.run_sha256 = run_sha256

    async def on_job_start(self, job):
        job.on_agent_started(self.before_agent)

    async def on_job_end(self, job_result):
        pass

    def bind_live(self, project, trial_dir):
        return bound_inference_containers(project, self.agent_image, self.egress_image, trial_dir)

    async def before_agent(self, event):
        trial = event.trial_name
        if not trial.startswith(self.scope) or not re.fullmatch(r'[A-Za-z0-9_-]+', trial):
            raise ValueError('trial outside the qualified Docker scope')
        project = trial.lower() + '__env'
        if event.config.agent.extra_allowed_hosts != [INFERENCE_HOST]:
            raise ValueError('unexpected native inference network plan')
        trial_dir = Path(event.config.trials_dir) / trial
        proof = await asyncio.to_thread(self.bind_live, project, trial_dir)
        trial_id = str(UUID(str(event.result.id)))
        binding = json.dumps({'run_sha256': self.run_sha256, 'trial': trial, 'trial_id': trial_id}, sort_keys=True)
        await asyncio.to_thread(docker_lines, 'exec', '--user', '0:0', proof['main'], '/bin/sh', '-c',
                                'set -C; umask 077; printf "%s\\n" "$1" > "$2"', 'sh', binding, BINDING)
        path = trial_dir / RECEIPT
        with path.open('x', encoding='utf-8') as stream:
            json.dump(proof, stream, sort_keys=True)
            stream.write('\n')
