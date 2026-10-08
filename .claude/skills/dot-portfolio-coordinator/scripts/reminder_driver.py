"""One trusted AGY generation; process completion is never delivery evidence."""
import json
import math
from pathlib import Path
from reminder_process import run


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('duplicate JSON field')
    return result


def generate(executable, prompt_path, timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError('invalid generation timeout')
    with Path(prompt_path).open('rb') as source:
        prompt = source.read(65537).decode('utf-8')
    message = json.dumps({'event': 'user', 'message': {'content': prompt}}, ensure_ascii=False) + '\n'
    payload = message.encode('utf-8')
    if not prompt.strip() or len(payload) > 65536:
        raise ValueError('invalid generation prompt')
    argv = [executable, '--dangerously-skip-permissions', '--new-project',
            '--print-timeout', f'{timeout}s', '--input-format', 'stream-json',
            '--output-format', 'stream-json']
    receipt = run(argv, payload, timeout=timeout, max_input=65536, max_output=65536)
    if (type(receipt['returncode']) is not int or receipt['returncode'] != 0 or
            receipt['reason'] != 'exited' or receipt['natural_exit'] is not True or
            receipt['cleanup_ok'] is not True or receipt['forced_cleanup'] is not False):
        raise ValueError('generation process failed')
    events = [json.loads(line, object_pairs_hook=unique_object)
              for line in receipt['stdout'].decode('utf-8').splitlines()]
    if (not events or any(not isinstance(event, dict) or not isinstance(event.get('event'), str)
                          for event in events) or
            sum(event['event'] == 'result' for event in events) != 1 or
            events[-1]['event'] != 'result'):
        raise ValueError('invalid terminal envelope')
    result = events[-1].get('result')
    if not isinstance(result, dict) or result.get('status') != 'SUCCESS':
        raise ValueError('generation unsuccessful')
    response = result.get('response')
    if not isinstance(response, str) or not response.strip() or len(response) > 1200:
        raise ValueError('invalid reminder text')
    response.encode('utf-8')
    return response
