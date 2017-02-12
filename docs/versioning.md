As a base we took http://semver.org/ but we have some minor differences.

_Note: latest KD releases has slightly deviated from this policy, but we believe open source version will use it more strictly_

Kuberdock will use such scheme:

**X.Y.Z-B**

Where:

**X** - major version, should be increased only when some big changes are introduced, including lots of new features, even possibly in backward incompatible way (this is a more exceptions, then rule itself, and should be announced separately if happens)

**Y** - minor version, should be increased when new features are introduced in this release. At least one. Or we have changed some existing features (in backward compatible way).

**Z** - fixes version (or so-called patch version, it does not matter). Increased when we do only bug fixes and/or security fixes but don't change any features or add new.

**B** - is a special part. This part supposed to be always 1 and increased ONLY in cases where we want that upgrade system skip some packages during upgrade. This may happens when we release some package to stable repo and suddenly found that we have critical bug there and we don't want that clients can be upgraded to this broken release. We have two possible solutions - 1. Contact our admin to delete this package from repos (wrong and long way) or 2. somehow tell KD upgrade system to skip this package and not suggest it as a next upgrade(good way).
In that case all we need to do is release new FIXED KD package with SAME X.Y.Z but with increased -B.

For example, let's say we have in repo such KD versions:
```bash
    kd-1.0.0-1
    kd-1.1.0-1    # let's say here, we realized that we have huge critical issue that we don't want our clients to even see. So we just bump **B** to skip package for upgrade
    kd-1.1.0-2    # here, we tried to fix it, but do even worse)
    kd-1.1.0-3    # finally correct release
    kd-1.2.0-1
```

For the client that has installed KD 1.0.0-1 and want to upgrade it, sequence of upgrades will be next:

_1.0.0-1 ->  1.1.0-3 -> 1.2.0-1_

KD of versions 1.1.0-1 and 1.1.0-2 was skipped by upgrade utility, as we wanted, and clients are happy.
