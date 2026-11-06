---
name: automation-publish
description: Route package releases through the package owner's current release workflow.
---

# Package Release Entry Point

This shared catalog entry does not define package-specific build, cleanup,
installation, publication, or scheduler commands. Resolve the actual source
repository and release documentation from the package being released, then
follow that owner's current workflow.

## Release workflow

1. Resolve the package source and owner from the active repository and package
   metadata. Do not infer package names, versions, or repositories from this
   skill's name.
2. Read the release instructions maintained by that package's owner, including
   its versioning, artifact, publishing, and installation checks.
3. Keep each release artifact and verification environment scoped to the
   package owner's workflow. Do not uninstall packages from the active Python
   environment or remove build outputs using unresolved globs.
4. Verify the requested release result from the owner's artifacts and checks.
   A process start, successful upload request, or package import alone does not
   prove the complete release.
5. Follow the current Git push procedure for any source commit: verify the
   branch, upstream, and explicit target first, and preserve CLI/model
   provenance in the commit message.
6. Run only scheduled jobs that are part of the requested task. Inspect their
   current configuration without displaying credential-bearing schedule lines;
   do not terminate existing processes by name or launch every configured job.

## Scope

This entry point directs work to the package-specific release owner. It does
not supply a generic release recipe or claim that any package is installed,
published, or running.
