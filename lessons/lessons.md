# Lessons — golf-sim

## [2026-07-02][mirror-symmetric-tests] Symmetric pipeline tests cannot catch mirrored sign conventions
- **Phase:** verification
- **Mistake:** The whole suite passed while azimuth/side-spin/offline were
  labeled "+right" but mapped to +Y, which is *left* in the right-handed
  world frame (X downrange, Z up). Tests generated truth and recovered it
  through the same mirrored mapping, so the flip cancelled.
- **Root cause:** Every test was truth→synthesize→recover symmetric; nothing
  pinned a signed output to an absolute physical direction.
- **Fix:** tests/test_conventions.py asserts absolute directions (+azimuth →
  offline_m > 0 → "R"; backspin Magnus is +Z), and all flips go through
  constants.WORLD_Y_PER_GOLF_RIGHT.
- **Prevention:** For any measurement system, add at least one test per
  signed quantity that anchors it to a physically-derived absolute reference,
  not to a round-trip.

## [2026-07-02][carry-only-fit] Fitting a flight model to carry alone flies the wrong shape
- **Phase:** physics validation
- **Mistake:** Aero constants tuned to carry only matched carry within ~4 yd
  while irons flew ~20% too flat (7-iron apex 77 ft vs 96 ft measured,
  descent 40° vs 50°).
- **Root cause:** Carry is a single scalar; many (Cd, Cl) pairs reproduce it
  with wrong trajectory shape. Apex + descent constrain the shape.
- **Fix:** scripts/fit_aero.py fits carry+apex+descent simultaneously with a
  Reynolds(speed)-dependent Cd; hold-out refit (--holdout) proves
  generalisation; regression test asserts all three per club.
- **Prevention:** Validate simulated trajectories on shape metrics, not just
  endpoint distance.

## [2026-07-02][ordering-sign-luck] Tests passed on an arbitrary SVD sign
- **Phase:** review
- **Mistake:** detect_ordered ordered strobe blobs along an SVD principal
  axis whose sign is arbitrary; tests passed because LAPACK's sign happened
  to align for the default geometry.
- **Root cause:** No physical anchor for temporal order.
- **Fix:** Order by projection onto the tee→track direction (reference_uv),
  plus a flies-downrange refit guard and a max_reproj_px pairing gate in
  process_shot.
- **Prevention:** Never rely on an eigenvector/SVD sign; anchor orderings to
  a physical reference, and gate multi-sensor pairing on a consistency
  metric (reprojection error).
