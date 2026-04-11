from core import seed_music_generator
from core.seed_generation_planner import (
    PhrasePlan,
    VariantBehavior,
    build_phrase_plan,
    build_variant_behavior,
    chord_root_degree,
)
from core.seed_generation_utils import get_rng_from_seed
from core.seed_style_catalog import SeedMusicStyle


def test_build_phrase_plan_tracks_intro_and_phrase_boundaries():
    plan = build_phrase_plan(length_bars=16, intro_bars=2, phrase_lengths=[4, 4, 4, 4])

    assert isinstance(plan, PhrasePlan)
    assert plan.phrase_lengths == (4, 4, 4, 2)
    assert plan.phrase_starts == (0, 4, 8, 12)
    assert plan.phrase_index_at_bar(0) == -1
    assert plan.phrase_index_at_bar(2) == 0
    assert plan.phrase_index_at_bar(15) == 3


def test_phrase_plan_reports_roles_progress_and_phrase_end():
    plan = build_phrase_plan(length_bars=18, intro_bars=2, phrase_lengths=[4, 4, 4, 4])

    assert plan.phrase_role_at_bar(0) == "intro"
    assert plan.phrase_role_at_bar(2) == "statement"
    assert plan.phrase_role_at_bar(6) == "development"
    assert plan.phrase_role_at_bar(10) == "variation"
    assert plan.phrase_role_at_bar(14) == "resolution"
    assert plan.phrase_progress_at_bar(3, 0) == 0.25
    assert plan.is_phrase_end(17, 3) is True


def test_build_variant_behavior_for_suspense_plans_quiet_bars():
    rng = get_rng_from_seed("planner-quiet-bars")
    behavior = build_variant_behavior(
        style=SeedMusicStyle.SUSPENSE,
        variant_id="suspense_sparse",
        rng=rng,
        length_bars=16,
    )

    assert isinstance(behavior, VariantBehavior)
    assert behavior.is_suspense_sparse is True
    assert all(bar_idx % 4 in (1, 3) for bar_idx in behavior.quiet_bars)


def test_build_variant_behavior_for_battle_sets_variant_flags():
    rng = get_rng_from_seed("planner-battle")
    behavior = build_variant_behavior(
        style=SeedMusicStyle.BATTLE,
        variant_id="battle_drums",
        rng=rng,
        length_bars=16,
    )

    assert behavior.is_battle_drums is True
    assert behavior.is_battle_melody is False
    assert behavior.quiet_bars == frozenset()


def test_chord_root_degree_is_zero_based():
    assert chord_root_degree(1) == 0
    assert chord_root_degree(5) == 4
    assert chord_root_degree(8) == 0


def test_seed_music_generator_keeps_planner_re_exports():
    assert seed_music_generator.PhrasePlan is PhrasePlan
    assert seed_music_generator.VariantBehavior is VariantBehavior
    assert seed_music_generator.build_phrase_plan is build_phrase_plan
    assert seed_music_generator.build_variant_behavior is build_variant_behavior
    assert seed_music_generator.chord_root_degree is chord_root_degree
