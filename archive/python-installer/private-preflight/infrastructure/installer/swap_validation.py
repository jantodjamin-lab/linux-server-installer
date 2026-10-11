"""Independent pure POST assessment; does not consume execution success flags."""
from dataclasses import replace
from infrastructure.installer.swap_step import Plan, Observation, Context, Stop, conditions


def validate_post(plan: Plan, pre: Observation, post: Observation, context: Context):
    try:
        clean_pre = bool(conditions(plan, pre, context))
    except (Stop, TypeError, ValueError):
        clean_pre = False
    checks = {
        'clean_pre': clean_pre,
        'identity': post.identity == pre.identity == context.identity,
        'fresh_complete': (post.complete is True and post.compatible is True and
                           post.preflight == 'PASS' and
                           pre.observed_at <= post.observed_at <= context.now and
                           0 <= context.now-post.observed_at <= context.max_age),
        'size_active': (post.file_bytes == plan.size_bytes and
                        post.active == ((plan.path, plan.active_bytes),)),
        'owner_mode': post.uid == post.gid == 0 and post.mode == 0o600,
        'fstab_backup': (pre.fstab == plan.fstab_before and
                         post.fstab == plan.fstab_after and post.backup == pre.fstab),
        'no_side_effects': (post.unchanged == pre.unchanged and
                            post.free_bytes == pre.free_bytes - plan.size_bytes and
                            post.free_bytes >= plan.reserve_bytes),
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'installation_authorized': False}


def compare_runs(plan: Plan, pre1: Observation, post1: Observation, ctx1: Context,
                 pre2: Observation, post2: Observation, ctx2: Context):
    """Only time and reviewed generation/boot-id differ. Raw evidence retained."""
    for pre, post, ctx in ((pre1, post1, ctx1), (pre2, post2, ctx2)):
        if validate_post(plan, pre, post, ctx)['status'] != 'PASS':
            raise Stop('Missing/failed independent POST')
        if not conditions(plan, pre, ctx):
            raise Stop('Run requires clean PRE, not an idempotent rerun')
        if pre.file_bytes or pre.active or pre.backup is not None:
            raise Stop('Run must start from clean restored snapshot')
    if (pre1.identity[3] == pre2.identity[3] or
            pre1.identity[:3] + pre1.identity[4:5] != pre2.identity[:3] + pre2.identity[4:5]):
        raise Stop('Restore generation or independently reviewed identity mismatch')
    def normalize(state):
        return replace(state, observed_at=0,
                       identity=state.identity[:3] + ('<reviewed-generation>',) +
                       state.identity[4:5] + ('<reviewed-boot>',))
    same = normalize(pre1) == normalize(pre2) and normalize(post1) == normalize(post2)
    return {'status': 'PASS' if same else 'FAIL', 'installation_authorized': False}
