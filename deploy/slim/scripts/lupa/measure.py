#!/usr/bin/env python3
"""Capture comparable Docker and runtime storage figures without container secrets."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path


def output(*cmd):
    return subprocess.check_output(cmd, text=True).strip()


def measure(image, container):
    image_info = json.loads(output('docker', 'image', 'inspect', image, '--format',
        '{"id":{{json .Id}},"docker_reported_bytes":{{.Size}},"descriptor":{{json .Descriptor}}}'))
    # Docker Engine's containerd image store keeps the exact registry descriptors.
    store = Path('/var/lib/containerd/io.containerd.content.v1.content/blobs/sha256')
    try:
        manifest = json.loads((store / image_info['descriptor']['digest'].split(':')[1]).read_text())
        if 'manifests' in manifest:
            desc = next(d for d in manifest['manifests'] if d.get('platform', {}).get('architecture') == 'amd64' and d.get('platform', {}).get('os') == 'linux')
            manifest = json.loads((store / desc['digest'].split(':')[1]).read_text())
        image_info['registry_layer_bytes'] = sum(layer['size'] for layer in manifest['layers'])
        image_info['registry_layer_media_types'] = sorted(set(layer['mediaType'] for layer in manifest['layers']))
    except (FileNotFoundError, KeyError, StopIteration):
        image_info['registry_layer_bytes'] = None
    rootfs = json.loads(output('docker', 'container', 'inspect', '--size', container, '--format',
        '{"writable_bytes":{{.SizeRw}},"rootfs_bytes":{{.SizeRootFs}}}'))
    sizes = {}
    for path in ('/config', '/app/node_modules'):
        sizes[path] = int(output('docker', 'exec', container, 'du', '-sb', path).split()[0])
    return {'image': image, 'container': container, **image_info, **rootfs,
            'directories_bytes': sizes,
            'rootfs_plus_config_bytes': rootfs['rootfs_bytes'] + sizes['/config']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='reports/sizes.json')
    parser.add_argument('--slim-container', default='debina-lupa-lupa-1')
    parser.add_argument('--slim-image', default='debina/lupa:slim-testing')
    args = parser.parse_args()
    result = {'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'notes': ['Docker reported image size is compared with the same engine/metric.',
                        'rootfs_bytes is the merged container filesystem including writable changes.',
                        'Directory sizes are apparent bytes, not allocated filesystem blocks.',
                        'Original /app/node_modules is an additional host bind mount; slim embeds it.',
                        'Build cache and shared image layers are not per-instance runtime costs.'],
              'original': measure('ghcr.io/linuxserver/baseimage-selkies:debiantrixie','lupa-lupa-1'),
              'slim': measure(args.slim_image,args.slim_container)}
    original = result['original']
    slim = result['slim']
    original['runtime_total_bytes'] = original['rootfs_plus_config_bytes'] + original['directories_bytes']['/app/node_modules']
    slim['runtime_total_bytes'] = slim['rootfs_plus_config_bytes']
    result['image_reduction_percent'] = round(100*(1-slim['docker_reported_bytes']/original['docker_reported_bytes']),2)
    result['runtime_reduction_percent'] = round(100*(1-slim['runtime_total_bytes']/original['runtime_total_bytes']),2)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
