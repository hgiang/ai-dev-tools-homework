"""Who is in a chore's rotation, and whose turn comes next.

Every function here reads the rotation and returns new lists; nothing is
mutated or saved.
"""


def _active(members):
    return [member for member in members if member.is_active]


def rotation_members(chore):
    """Every member in the chore's rotation in slot order, active or not."""
    return [slot.member for slot in chore.rotation_slots.select_related("member")]


def active_rotation(chore):
    """Members eligible for assignment, in slot order, inactive ones omitted."""
    return _active(rotation_members(chore))


def next_member(chore, after):
    """The member whose turn follows `after`, skipping inactive members.

    Wraps past the end of the rotation, so a single-member rotation returns
    that member. Returns None when the chore has no active members.

    `after` may be None or a member who has since left the rotation; either
    way the rotation starts from the top.
    """
    order = rotation_members(chore)
    active = _active(order)
    if not active:
        return None
    if after is None or after not in order:
        return active[0]

    start = order.index(after)
    # Everything after `after`, then wrapping back around through `after`.
    rotated = order[start + 1 :] + order[: start + 1]
    return next(member for member in rotated if member.is_active)
