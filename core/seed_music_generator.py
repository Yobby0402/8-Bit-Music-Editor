"""
鍩轰簬 Seed 鐨勭畝鍗?8bit 闊充箰鐢熸垚鍣紙V3 瑙勫垝鐨勭涓€姝ワ級

鐩爣锛氱被浼?Minecraft 鐨勪笘鐣岀敓鎴愶紝鐢ㄤ竴涓?seed 鐢熸垚涓€娈电畝鍗曚絾鍙紪杈戠殑闊充箰銆?褰撳墠瀹炵幇锛氭渶灏忓彲鐢ㄧ増鏈紝鍙敓鎴愪竴涓富鏃嬪緥杞ㄩ亾锛岀敤浜庨獙璇佹祦绋嬪拰鍙噸澶嶆€с€?
閲嶆瀯鐗堟湰锛氫娇鐢ㄩ鏍奸厤缃被绯荤粺锛屾瘡涓鏍肩嫭绔嬬鐞嗗叾鐢熸垚閫昏緫銆?"""

from typing import Optional, Union

from . import seed_generation_planner as generation_planner
from . import seed_generation_utils as generation_utils
from . import seed_structure_catalog as structure_catalog
from . import seed_style_catalog as style_catalog
from . import seed_style_configs as style_configs
from . import seed_track_builders as track_builders
from .models import Note, Project, Track, TrackType
from .seed_style_catalog import SeedMusicStyle, get_style_meta, get_style_params
from .seed_free_form import (
    bars_progression_free,
    expand_motifs_with_procedural_fragments,
    merge_progression_degrees,
    random_intro_bars,
    random_phrase_partition,
)
from .variation_spec import VariationSpec, build_rng_family, filter_motifs_by_bank

RUNTIME_STYLE_OVERRIDES = style_catalog.RUNTIME_STYLE_OVERRIDES
STYLE_META = style_catalog.STYLE_META
STYLE_PARAMS_MAP = style_catalog.STYLE_PARAMS_MAP
STYLE_VARIANT_META = style_catalog.STYLE_VARIANT_META
StyleParams = style_catalog.StyleParams
clear_style_runtime_override = style_catalog.clear_style_runtime_override
get_style_variants = style_catalog.get_style_variants
set_style_runtime_override = style_catalog.set_style_runtime_override

MusicStyleConfig = style_configs.MusicStyleConfig
Classic8bitStyleConfig = style_configs.Classic8bitStyleConfig
LofiStyleConfig = style_configs.LofiStyleConfig
BattleStyleConfig = style_configs.BattleStyleConfig
SuspenseStyleConfig = style_configs.SuspenseStyleConfig
CalmStyleConfig = style_configs.CalmStyleConfig
RockStyleConfig = style_configs.RockStyleConfig
WorkshopStyleConfig = style_configs.WorkshopStyleConfig
DanceStyleConfig = style_configs.DanceStyleConfig
get_style_config = style_configs.get_style_config
MUSIC_STRUCTURE_PRESETS = structure_catalog.MUSIC_STRUCTURE_PRESETS
get_structure_for_bars = structure_catalog.get_structure_for_bars
get_rng_from_seed = generation_utils.get_rng_from_seed
_pick_with_weights = generation_utils._pick_with_weights
PhrasePlan = generation_planner.PhrasePlan
VariantBehavior = generation_planner.VariantBehavior
build_phrase_plan = generation_planner.build_phrase_plan
build_variant_behavior = generation_planner.build_variant_behavior
chord_root_degree = generation_planner.chord_root_degree
TrackBuildContext = track_builders.TrackBuildContext
build_bass_track = track_builders.build_bass_track
build_harmony_track = track_builders.build_harmony_track
build_drum_track = track_builders.build_drum_track


def generate_simple_project_from_seed(
    seed: Union[int, str],
    length_bars: int = 16,
    style: SeedMusicStyle = SeedMusicStyle.CLASSIC_8BIT,
    variant_id: str = "default",
    enable_bass: bool = True,
    enable_harmony: bool = True,
    enable_drums: bool = True,
    variation: Optional[VariationSpec] = None,
) -> Project:
    """
    浣跨敤 seed 鐢熸垚涓€涓畝鍗曚絾鏇存湁銆屼箰鍙ユ劅銆嶇殑 8bit 椤圭洰锛堢洰鍓嶏細鍗曚富鏃嬪緥杞級銆?

    娑﹁壊閫昏緫锛堢浉瀵逛笂涓€鐗堢殑鎻愬崌锛夛細
    - 鏈夋槑纭殑灏忚妭缁撴瀯鍜屽拰澹拌蛋鍚戯紙I鈥揤鈥搗i鈥揑V / I鈥揑V鈥揤鈥揑 绛夋ā鏉匡級銆?
    - 浣跨敤鐭€屽姩鏈烘ā寮忋€嶏紙鐩稿闊崇骇 + 鑺傚锛夊苟閲嶅 / 寰皟锛屽舰鎴愬彲杈ㄨ瘑涔愬彞銆?
    - 寮烘媿 / 灏忚妭寮€澶翠紭鍏堜娇鐢ㄥ拰寮﹀唴闊筹紝寮辨媿浣跨敤缁忚繃闊虫垨閭婚煶銆?
    - 绠€鍗曠殑鍙ュ紡杞粨锛氬墠涓ゅ彞鐩镐技锛屽悗涓ゅ彞鍋氬皬鍙樺寲鎴栨媺楂樼粨灏俱€?
    """
    family = build_rng_family(seed, style.value, variation)
    structure_rng = family.structure
    melody_rng = family.melody
    bass_rng = family.bass
    harmony_rng = family.harmony
    drum_rng = family.drums
    drum_density = 5
    if variation is not None and variation.is_active():
        drum_density = variation.knob(1, 5)

    free_form = bool(variation and variation.free_form_layout)

    style_params = get_style_params(style)
    
    # 鑾峰彇椋庢牸閰嶇疆绫?
    style_config = get_style_config(style)

    # ---- 鍏ㄥ眬鍙傛暟锛堥殢椋庢牸鐣ユ湁鍙樺寲锛?---
    # 浣跨敤 STYLE_META 涓殑榛樿 BPM锛屼繚璇?UI 灞曠ず涓庣敓鎴愰€昏緫瀹屽叏涓€鑷?
    meta_bpm = get_style_meta(style)["default_bpm"]
    if free_form:
        bpm = int(round(meta_bpm * (0.88 + structure_rng.random() * 0.24)))
        bpm = max(50, min(220, bpm))
    else:
        bpm = meta_bpm
    beats_per_bar = 4.0  # 4/4 鎷?
    # 闀垮害闄愬埗锛氭渶灏?灏忚妭锛堣嚦灏戦棶-绛旂粨鏋勶級锛屾渶澶?28灏忚妭锛堝畬鏁存洸瀛愶級
    length_bars = max(8, min(length_bars, 128))
    total_beats = length_bars * beats_per_bar
    beat_duration = 60.0 / bpm

    project = Project(name=f"Seed Music ({seed})", bpm=bpm)

    # ---- 缁撴瀯灞傦細鏍规嵁棰勮鍐冲畾涔愬彞缁撴瀯 ----
    if free_form:
        intro_bars = random_intro_bars(length_bars, structure_rng)
        main_bars = length_bars - intro_bars
        phrase_lengths = random_phrase_partition(main_bars, structure_rng)
        phrase_plan = build_phrase_plan(length_bars, intro_bars, phrase_lengths)
    else:
        structure = get_structure_for_bars(length_bars)
        # 绋嬪簭鑷姩鍐冲畾 Intro锛氬浜?8 灏忚妭鍙婁互涓婏紝鍓?2 灏忚妭浣滀负 Intro
        intro_bars = 2 if length_bars >= 8 else 0
        phrase_plan = build_phrase_plan(length_bars, intro_bars, structure["phrases"])

    # ---- 椋庢牸鍙樹綋寮€鍏筹紙涓嶆敼鍙橀粯璁よ涓猴紝鍙湪瀵瑰簲鍙樹綋涓嬪仛杞婚噺璋冩暣锛?---
    variant_behavior = build_variant_behavior(style, variant_id, structure_rng, length_bars)
    is_battle_melody = variant_behavior.is_battle_melody
    is_battle_drums = variant_behavior.is_battle_drums
    is_suspense_dense = variant_behavior.is_suspense_dense
    is_suspense_sparse = variant_behavior.is_suspense_sparse
    quiet_bars = variant_behavior.quiet_bars

    # ---- 璋冨紡涓庨煶闃讹紙浣跨敤閰嶇疆绫伙級----
    root_midi, mode_name, scale_offsets = style_config.get_scale_choices(structure_rng)

    # 搴曞眰鍜屽０锛氱敤鍜屽鸡绾ф暟锛?=I,4=IV,5=V,6=vi,2=ii锛?
    # 浣跨敤閰嶇疆绫昏幏鍙栧拰寮﹁繘琛屾ā鏉?
    progression_templates = style_config.get_chord_progression_templates(structure_rng)
    if free_form:
        deg_pool = merge_progression_degrees(progression_templates, structure_rng)
        bars_progression = bars_progression_free(length_bars, deg_pool, structure_rng)
    else:
        prog = structure_rng.choice(progression_templates)
        # 鏍规嵁灏忚妭鏁伴噸澶?/ 鎴柇
        bars_progression = [prog[i % len(prog)] for i in range(length_bars)]

    # ---- 鍔ㄦ満妯″紡锛氱浉瀵归煶绾?+ 鑺傚 ----
    # 使用配置类获取该风格的动机模式
    motifs = style_config.get_melody_motifs(melody_rng, variant_id)
    if free_form:
        motifs = expand_motifs_with_procedural_fragments(motifs, melody_rng)
    elif variation is not None and variation.is_active():
        motifs = filter_motifs_by_bank(motifs, variation.knob(0, 5))
    melody_track = Track(name="Seed 主旋律", track_type=TrackType.NOTE_TRACK)
    # 浣跨敤椋庢牸閰嶇疆鐨?ADSR锛岃€屼笉鏄湪杩欓噷鍐欐
    melody_adsr = style_params.melody_adsr

    last_pitch = root_midi + scale_offsets[chord_root_degree(bars_progression[0])]
    # 鎺у埗鏁翠綋闊冲煙锛氶伩鍏嶆棆寰嬭窇寰楄繃楂樻垨杩囦綆
    pitch_min = root_midi - 5
    pitch_max = root_midi + 14

    # ---- 鏀硅繘2锛氫富棰?鍙樺-鍥炲綊鐨勫姩鏈洪€夋嫨 ----
    # 涓烘瘡涓箰鍙ラ€夋嫨涓€涓?涓婚鍔ㄦ満"锛屽悗缁箰鍙ュ熀浜庝富棰樿繘琛屽彉濂?
    theme_motif = None  # 涓婚鍔ㄦ満锛堢涓€涓箰鍙ヤ娇鐢級
    phrase_motifs = {}  # 姣忎釜涔愬彞浣跨敤鐨勫姩鏈?
    
    # 鍏堝鐞咺ntro閮ㄥ垎锛堝鏋滄湁锛?
    # 鎽囨粴椋庢牸锛氬墠1-2灏忚妭瀹屽叏鍙湁榧撶偣锛屼富鏃嬪緥寤惰繜杩涘叆
    # 鑸炴洸椋庢牸锛欼ntro閮ㄥ垎绾紦鐐癸紝鍜屽０鍏堣繘鍏ワ紝涓绘棆寰嬬◢鍚庤繘鍏?
    dance_melody_start_bar = 0
    dance_harmony_start_bar = 0
    if not free_form and style == SeedMusicStyle.DANCE and intro_bars >= 1:
        # 鑸炴洸椋庢牸锛氬墠1-2灏忚妭绾紦鐐癸紝鍜屽０浠庣2灏忚妭寮€濮嬶紝涓绘棆寰嬩粠绗?灏忚妭寮€濮?
        dance_drum_only_bars = min(2, intro_bars)  # 鏈€澶?灏忚妭绾紦鐐?
        dance_harmony_start_bar = dance_drum_only_bars  # 鍜屽０浠庣2灏忚妭寮€濮嬶紙濡傛灉鏈?灏忚妭Intro锛?
        dance_melody_start_bar = dance_drum_only_bars + 1  # 涓绘棆寰嬩粠绗?灏忚妭寮€濮嬶紙濡傛灉鏈?灏忚妭Intro锛?
        # 濡傛灉鍙湁1灏忚妭Intro锛屽拰澹颁粠绗?灏忚妭寮€濮嬶紝涓绘棆寰嬩粠绗?灏忚妭寮€濮?
        if intro_bars == 1:
            dance_harmony_start_bar = 0  # 鍜屽０浠庣1灏忚妭寮€濮?
            dance_melody_start_bar = 1  # 涓绘棆寰嬩粠绗?灏忚妭寮€濮?
    
    if not free_form and style == SeedMusicStyle.ROCK and intro_bars >= 2:
        # 鎽囨粴椋庢牸锛氬墠1-2灏忚妭绾紦鐐癸紝涓绘棆寰嬩粠绗?灏忚妭寮€濮嬶紙濡傛灉鏈?灏忚妭Intro锛?
        # 鎴栬€呬粠绗?灏忚妭鍚庡崐娈靛紑濮嬶紙濡傛灉鍙湁1灏忚妭Intro锛?
        rock_drum_only_bars = min(2, intro_bars)  # 鏈€澶?灏忚妭绾紦鐐?
        rock_melody_start_bar = rock_drum_only_bars  # 涓绘棆寰嬩粠杩欎釜浣嶇疆寮€濮?
        
        # 绾紦鐐瑰皬鑺傦細涓嶇敓鎴愪富鏃嬪緥
        for bar_idx in range(rock_drum_only_bars):
            # 杩欎簺灏忚妭瀹屽叏璺宠繃涓绘棆寰嬬敓鎴愶紝鍙繚鐣欓紦鐐?
            pass
        
        # 涓绘棆寰嬪欢杩熻繘鍏ワ細浠巖ock_melody_start_bar寮€濮嬬敓鎴怚ntro鏃嬪緥
        for bar_idx in range(rock_melody_start_bar, intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro閮ㄥ垎锛氫娇鐢ㄧ畝鍗曠殑鍔ㄦ満锛屼笉鍙備笌涔愬彞缁撴瀯
            motif = melody_rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(pitch_min, min(pitch, pitch_max))
                
                start_time = global_beat * beat_duration
                # 涓绘棆寰嬪欢杩熻繘鍏ユ椂锛屽姏搴﹂€愭笎澧炲己
                progress = (bar_idx - rock_melody_start_bar) / max(1, intro_bars - rock_melody_start_bar)
                base_velocity = int(80 * (0.5 + 0.5 * progress))  # 浠?0%閫愭笎澧炲己鍒?00%
                
                duration_beats_for_time = dur_beats
                duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    elif not free_form and style == SeedMusicStyle.DANCE and intro_bars >= 1:
        # 鑸炴洸椋庢牸锛氬墠1-2灏忚妭绾紦鐐癸紝涓绘棆寰嬩粠绗?灏忚妭寮€濮?
        # 涓绘棆寰嬪欢杩熻繘鍏ワ細浠巇ance_melody_start_bar寮€濮嬬敓鎴怚ntro鏃嬪緥
        for bar_idx in range(dance_melody_start_bar, intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro閮ㄥ垎锛氫娇鐢ㄧ畝鍗曠殑鍔ㄦ満锛屼笉鍙備笌涔愬彞缁撴瀯
            motif = melody_rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(60, min(84, pitch))  # 闄愬埗鍦–4-C6鑼冨洿
                
                start_time = global_beat * beat_duration
                duration = dur_beats * beat_duration
                
                # 鑸炴洸锛欼ntro閮ㄥ垎涓绘棆寰嬮€愭笎澧炲己
                progress = (bar_idx - dance_melody_start_bar) / max(1, intro_bars - dance_melody_start_bar)
                base_velocity = int(85 * (0.6 + 0.4 * progress))  # 浠?0%閫愭笎澧炲己鍒?00%
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    else:
        # 鍏朵粬椋庢牸锛氭甯哥殑Intro澶勭悊
        for bar_idx in range(intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro閮ㄥ垎锛氫娇鐢ㄧ畝鍗曠殑鍔ㄦ満锛屼笉鍙備笌涔愬彞缁撴瀯
            motif = melody_rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(pitch_min, min(pitch, pitch_max))
                
                start_time = global_beat * beat_duration
                base_velocity = int(80 * 0.65)  # Intro閮ㄥ垎鍔涘害寰堝急
                
                duration_beats_for_time = dur_beats
                duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    
    # 澶勭悊涓绘棆寰嬮儴鍒嗭紙甯︿箰鍙ョ粨鏋勶級
    # 鑸炴洸椋庢牸锛氫富鏃嬪緥浠巇ance_melody_start_bar寮€濮嬶紙濡傛灉dance_melody_start_bar > intro_bars锛?
    melody_start_bar = intro_bars
    if style == SeedMusicStyle.DANCE and dance_melody_start_bar > intro_bars:
        melody_start_bar = dance_melody_start_bar
    
    for bar_idx in range(melody_start_bar, length_bars):
        bar_start = bar_idx * beats_per_bar
        bar_chord_degree = bars_progression[bar_idx]
        bar_root_degree = chord_root_degree(bar_chord_degree)

        # 纭畾褰撳墠灏忚妭灞炰簬鍝釜涔愬彞
        phrase_idx = phrase_plan.phrase_index_at_bar(bar_idx)
        phrase_role = phrase_plan.phrase_role(phrase_idx)
        
        # 如果是乐句的第一小节，选择或生成动机
        phrase_start_bar = phrase_plan.phrase_start_bar(phrase_idx)
        is_phrase_start = (bar_idx == phrase_start_bar)
        
        if is_phrase_start:
            if free_form:
                phrase_motifs[phrase_idx] = melody_rng.choice(motifs)
            elif phrase_idx == 0:
                # 绗竴涓箰鍙ワ細閫夋嫨涓婚鍔ㄦ満
                theme_motif = melody_rng.choice(motifs)
                phrase_motifs[phrase_idx] = theme_motif
            else:
                # 鍚庣画涔愬彞锛氬熀浜庝富棰樿繘琛屽彉濂?
                if phrase_role == "answer":
                    # 绛斿彞锛氫娇鐢ㄤ富棰樼殑"闀滃儚"鎴?鍊掑奖"锛堜笂琛屽彉涓嬭锛屼笅琛屽彉涓婅锛?
                    theme = phrase_motifs.get(0, melody_rng.choice(motifs))
                    # 绠€鍗曞彉濂忥細鍙嶈浆鐩稿搴︽暟
                    phrase_motifs[phrase_idx] = [(-rel, dur) for rel, dur in theme]
                elif phrase_role == "variation":
                    # 鍙樺锛氫娇鐢ㄤ富棰樼殑鑺傚锛屼絾鏀瑰彉闊抽珮璧板悜
                    theme = phrase_motifs.get(0, melody_rng.choice(motifs))
                    # 淇濇寔鑺傚锛屾敼鍙橀煶楂樻ā寮?
                    phrase_motifs[phrase_idx] = [(rel + (1 if melody_rng.random() < 0.5 else -1), dur) for rel, dur in theme]
                elif phrase_role == "resolution":
                    # 瑙ｅ喅锛氬洖褰掍富棰橈紝浣嗙畝鍖?
                    theme = phrase_motifs.get(0, melody_rng.choice(motifs))
                    # 浣跨敤涓婚鐨勫墠鍗婇儴鍒?
                    phrase_motifs[phrase_idx] = theme[:len(theme)//2] if len(theme) > 2 else theme
                else:
                    # 鍏朵粬锛氱洿鎺ヤ娇鐢ㄤ富棰樻垨杞诲井鍙樺
                    if melody_rng.random() < 0.6:
                        phrase_motifs[phrase_idx] = phrase_motifs.get(0, melody_rng.choice(motifs))
                    else:
                        phrase_motifs[phrase_idx] = melody_rng.choice(motifs)
        
        # 鑾峰彇褰撳墠涔愬彞鐨勫姩鏈?
        motif = phrase_motifs.get(phrase_idx, melody_rng.choice(motifs))
        
        # 鍙ュ紡鎺у埗锛氭牴鎹箰鍙ヨ鑹茶皟鏁撮煶楂樹腑蹇?
        phrase_shift = 0
        if free_form:
            phrase_shift = melody_rng.randint(-1, 3)
        elif phrase_role == "variation":
            phrase_shift = 2  # 鍙樺涔愬彞鎶珮
        elif phrase_role == "resolution":
            phrase_shift = 0  # 瑙ｅ喅涔愬彞鍥炲綊
        elif phrase_role == "answer":
            phrase_shift = 1  # 绛斿彞鐣ュ井鎶珮

        # 鎽囨粴椋庢牸锛氬湪variation闃舵鐢熸垚solo锛堝揩閫熴€佸瘑闆嗙殑闊崇锛?
        if not free_form and style == SeedMusicStyle.ROCK and phrase_role == "variation":
            # Solo鐗瑰緛锛氬揩閫熴€佸瘑闆嗐€侀煶闃惰窇鍔?
            # 浣跨敤鍗佸叚鍒嗛煶绗︼紙0.25鎷嶏級鐢熸垚蹇€熻窇鍔紝纭繚瑕嗙洊鏁翠釜灏忚妭
            beat_in_bar = 0.0
            solo_last_degree = bar_root_degree  # 鍒濆鍖杝olo鐨勮捣濮嬪害鏁?
            dur_beats = 0.25  # 鍗佸叚鍒嗛煶绗?
            
            # 纭繚瑕嗙洊鏁翠釜灏忚妭锛氱敓鎴愬埌灏忚妭鏈熬锛屼笉鐣欎綑閲?
            # 璁＄畻鑳界敓鎴愬灏戜釜鍗佸叚鍒嗛煶绗︼紙姣忓皬鑺?鎷?= 16涓崄鍏垎闊崇锛?
            max_notes = int(beats_per_bar / dur_beats)  # 16涓崄鍏垎闊崇
            
            for note_idx in range(max_notes):
                beat_in_bar = note_idx * dur_beats
                # 纭繚涓嶈秴杩囧皬鑺傛湯灏?
                if beat_in_bar >= beats_per_bar:
                    break
                    
                global_beat = bar_start + beat_in_bar
                # 寮烘媿鍒ゆ柇锛氭瘡鎷嶇殑绗?涓崄鍏垎闊崇锛?.0, 1.0, 2.0, 3.0鎷嶏級
                is_strong_beat = abs(beat_in_bar % 1.0) < 1e-6
                
                # Solo闊抽珮閫夋嫨锛氬熀浜庡綋鍓嶅拰寮︼紝浣嗗厑璁告洿澶х殑璺宠繘鍜岄煶闃惰窇鍔?
                if is_strong_beat or note_idx == 0:
                    # 寮烘媿鎴栫涓€涓煶锛氫娇鐢ㄥ拰寮﹂煶
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                else:
                    # 寮辨媿锛氶煶闃惰窇鍔紙绾ц繘鎴栧皬璺筹級
                    if melody_rng.random() < 0.6:
                        # 60%姒傜巼绾ц繘锛?1鎴?1锛?
                        base_degree = solo_last_degree + melody_rng.choice([-1, 1])
                    else:
                        # 40%姒傜巼灏忚烦锛?2鎴?2锛?
                        base_degree = solo_last_degree + melody_rng.choice([-2, 2])
                
                # 鍙犲姞鍙ュ紡鍋忕Щ锛坴ariation闃舵鎶珮锛?
                base_degree += phrase_shift
                
                # 鍏佽鏇村ぇ鐨勯煶鍩熻寖鍥达紙solo鍙互鏇撮珮锛?
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                # Solo闊冲煙鍙互鏇撮珮
                solo_pitch_max = min(pitch_max + 12, 96)  # 鍏佽楂樹竴涓叓搴?
                pitch = max(pitch_min, min(pitch, solo_pitch_max))
                
                # Solo鍔涘害锛氬姩鎬佸彉鍖栵紝寮烘媿鏇撮噸
                if is_strong_beat:
                    solo_velocity = int(100 + melody_rng.uniform(-10, 15))
                else:
                    solo_velocity = int(85 + melody_rng.uniform(-10, 10))
                solo_velocity = max(70, min(127, solo_velocity))
                
                start_time = global_beat * beat_duration
                duration = dur_beats * beat_duration
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=solo_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                
                solo_last_degree = degree_clamped
        else:
            # 闈瀞olo閮ㄥ垎锛氭甯哥敓鎴?
            beat_in_bar = 0.0
            # 璁＄畻motif鐨勬€绘椂闀?
            motif_total_beats = sum(dur for _, dur in motif)
            
            # 濡傛灉motif鎬绘椂闀垮皬浜庡皬鑺傞暱搴︼紝闇€瑕侀噸澶峬otif鐩村埌濉弧鏁翠釜灏忚妭
            while beat_in_bar < beats_per_bar - 1e-6:
                # 閬嶅巻motif涓殑姣忎釜闊崇
                for rel_degree, dur_beats in motif:
                    if beat_in_bar >= beats_per_bar - 1e-6:
                        break

                    # 濡傛灉鍓╀綑鎷嶄笉澶燂紝缂╃煭鍒板皬鑺傛湯灏?
                    if beat_in_bar + dur_beats > beats_per_bar:
                        dur_beats = beats_per_bar - beat_in_bar

                    global_beat = bar_start + beat_in_bar

                    # 寮烘媿锛堝皬鑺傚ご / 绗?3 鎷嶏級浼樺厛鐢ㄤ笁鍜屽鸡鍐呴煶锛氭牴銆佷笁銆佷簲
                    is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6

                    # 鍦ㄨ妭濂忓眰闈㈠紩鍏ャ€屼紤姝€嶏細
                    # - 瀵瑰急鎷嶏紙闈?1/3 鎷嶏級锛屾湁涓€瀹氭鐜囨暣鎷嶅彉鎴愪紤姝紙涓嶅彂闊充絾鏃堕棿鍓嶈繘锛夛紱
                    # - 杩欐牱鍙互鍦ㄤ箰鍙ヤ腑浜х敓鍛煎惛鍜屾柇鍙ワ紝鑰屼笉浼氭敼鍙樻暣浣撹妭濂忕綉鏍笺€?
                    if not is_strong_beat:
                        # 椋庢牸鍖栧湴璋冩暣寮辨媿浼戞姒傜巼
                        if style == SeedMusicStyle.SUSPENSE:
                            # 鎮枒锛氶粯璁ら€傚害鐣欑櫧锛涙洿绱у紶 鈫?鏄庢樉鏇村皯浼戞锛涙洿绌虹伒 鈫?鏄庢樉鏇村浼戞
                            if is_suspense_dense:
                                rest_prob = 0.12
                            elif is_suspense_sparse:
                                rest_prob = 0.45
                            else:
                                rest_prob = 0.25
                        elif style == SeedMusicStyle.CALM:
                            rest_prob = 0.15  # 鑸掔紦锛氭棆寰嬫洿杩炶疮锛屽皯浼戞
                        elif style == SeedMusicStyle.LOFI:
                            rest_prob = 0.3   # Lofi锛氶€傚害鐣欑櫧
                        else:
                            rest_prob = 0.25  # 榛樿

                        # 涓洪伩鍏嶃€岄煶绗﹂兘闆嗕腑鍦ㄥ墠鍗婂皬鑺傘€嶏紝浠呭湪鍓?2 鎷嶅厑璁镐紤姝紝鍚?2 鎷嶄繚鎸佽緝楂樺～鍏呭害
                        if melody_rng.random() < rest_prob and beat_in_bar < beats_per_bar * 0.5:
                            beat_in_bar += dur_beats
                            continue
                    
                    if is_strong_beat:
                        if style == SeedMusicStyle.SUSPENSE:
                            # 鎮枒锛氬己鎷嶆湁鏇撮珮姒傜巼钀藉湪銆屽嵄闄╅煶銆嶏細鈾?銆佲櫗6銆佲櫗7锛堢浉瀵逛簬褰撳墠鍜屽鸡鏍归煶锛?
                            # 杩欓噷浣跨敤鐩稿搴︽暟 1, 5, 6锛堝搴?scale_offsets 涓殑鍗婇煶闃朵綅缃級
                            tense_choices = [1, 5, 6]
                            if melody_rng.random() < 0.6:
                                base_degree = bar_root_degree + melody_rng.choice(tense_choices)
                            else:
                                chord_tones = [0, 2, 4]  # 浠嶄繚鐣欏皯閲?1,3,5 浠ョ淮鎸佸彲鍚€?
                                base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                        else:
                            chord_tones = [0, 2, 4]  # 1,3,5
                            base_degree = bar_root_degree + melody_rng.choice(chord_tones)
                    else:
                        # 寮辨媿鍙互鐢ㄧ粡杩囬煶 / 閭婚煶锛堝湪鍜屽鸡搴︽暟闄勮繎娴姩锛?
                        base_degree = bar_root_degree + rel_degree
                        if style == SeedMusicStyle.SUSPENSE and melody_rng.random() < 0.25:
                            # 鍦ㄩ儴鍒嗗急鎷嶄笂澧炲姞鍗婇煶閭婚煶鎶栧姩锛屽埗閫犱笉瀹夌殑"鏃ユ湰灏忚皟"鍛抽亾
                            jitter = melody_rng.choice([-1, 1])
                            base_degree += jitter

                    # 鍙犲姞鍙ュ紡鍋忕Щ
                    base_degree += phrase_shift

                    # ---- 鏀硅繘3锛氬寮洪煶楂樻柟鍚戞劅锛堣鍒掍笂琛?涓嬭-鍥炲綊绾挎潯锛?---
                    # 鏍规嵁涔愬彞瑙掕壊鍜屼綅缃紝瑙勫垝鏃嬪緥绾挎潯鐨勬柟鍚?
                    phrase_progress = phrase_plan.phrase_progress_at_bar(bar_idx, phrase_idx)
                    
                    # 纭畾褰撳墠涔愬彞鐨勯煶楂樻柟鍚?
                    if phrase_role == "statement":
                        # 闄堣堪锛氬钩绋虫垨杞诲井涓婅
                        direction_bias = 0.3  # 杞诲井涓婅鍊惧悜
                    elif phrase_role == "development":
                        # 鍙戝睍锛氫笂琛岀Н绱?
                        direction_bias = 0.6
                    elif phrase_role == "variation":
                        # 鍙樺锛氳揪鍒伴珮鐐?
                        direction_bias = 0.8
                    elif phrase_role == "resolution":
                        # 瑙ｅ喅锛氫笅琛屽洖褰?
                        direction_bias = -0.4
                    elif phrase_role == "answer":
                        # 绛斿彞锛氬厛涓婂悗涓?
                        direction_bias = 0.4 if phrase_progress < 0.5 else -0.2
                    else:
                        direction_bias = 0.0
                    
                    # 鏍规嵁鏂瑰悜鍊惧悜璋冩暣闊抽珮
                    if direction_bias > 0:
                        # 涓婅鍊惧悜锛氬鍔犲害鏁?
                        base_degree += int(direction_bias * 2)
                    elif direction_bias < 0:
                        # 涓嬭鍊惧悜锛氬噺灏戝害鏁?
                        base_degree += int(direction_bias * 2)

                    # ---- 鏀硅繘5锛氬己鍖栬皟鎬т腑蹇冿紙鏇撮绻佸洖褰掍富闊筹級----
                    # 鍦ㄤ箰鍙ョ粨灏惧拰寮烘媿涓婏紝鏈夋洿楂樻鐜囧洖褰掍富闊?
                    tonic_degree = chord_root_degree(1)  # 涓婚煶搴︽暟
                    is_phrase_end = phrase_plan.is_phrase_end(bar_idx, phrase_idx)
                    
                    if is_phrase_end or (is_strong_beat and melody_rng.random() < 0.3):
                        # 涔愬彞缁撳熬鎴?0%鐨勫己鎷嶏細鍥炲綊涓婚煶
                        if abs(base_degree - tonic_degree) > 3:
                            # 濡傛灉绂讳富闊冲お杩滐紝鍚戜富闊抽潬鎷?
                            if base_degree > tonic_degree:
                                base_degree = tonic_degree + 2
                            else:
                                base_degree = tonic_degree - 2

                    # 鎺у埗鏃嬪緥娴佺晠锛氶伩鍏嶇涓婁竴涓煶璺冲お杩?
                    degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                    pitch = root_midi + scale_offsets[degree_clamped]
                    if abs(pitch - last_pitch) > 12:
                        # 濡傛灉璺冲お澶э紝寰€涓婁竴涓煶闈犳嫝涓€鐐癸紙榛樿鏈€澶х害浜斿害锛?
                        if pitch > last_pitch:
                            pitch = last_pitch + 7  # 浜斿害
                        else:
                            pitch = last_pitch - 7

                    # 鑸掔紦椋庢牸锛氳繘涓€姝ュ帇缂╄烦杩涳紝灏介噺鎺у埗鍦ㄤ簲搴︿互鍐?
                    if style == SeedMusicStyle.CALM and abs(pitch - last_pitch) > 7:
                        if pitch > last_pitch:
                            pitch = last_pitch + 5
                        else:
                            pitch = last_pitch - 5

                    # 闄愬埗鍦ㄦ暣浣撻煶鍩熻寖鍥村唴
                    pitch = max(pitch_min, min(pitch, pitch_max))

                    # 閬垮厤鍑虹幇銆屽悓涓€涓煶杩炵画鍑虹幇澶娆°€嶏細濡傛灉宸茬粡杩炵画涓ゆ鐩稿悓锛屽垯寮哄埗灏忕骇杩?
                    if len(melody_track.notes) >= 2:
                        if (melody_track.notes[-1].pitch == last_pitch and
                                melody_track.notes[-2].pitch == last_pitch and
                                pitch == last_pitch):
                            # 灏濊瘯寰€涓婃垨寰€涓嬪崐闊抽樁绉诲姩涓€涓煶闃跺害鏁?
                            adjust = 1 if melody_rng.random() < 0.5 else -1
                            adj_degree = degree_clamped + adjust
                            adj_degree = max(0, min(adj_degree, len(scale_offsets) - 1))
                            pitch = root_midi + scale_offsets[adj_degree]
                            pitch = max(pitch_min, min(pitch, pitch_max))

                    last_pitch = pitch
                    start_time = global_beat * beat_duration

                    # ---- 鏀硅繘4锛氭敼杩涜妭濂忓眰娆★紙绉疮-閲婃斁妯″紡锛?---
                    # 鏍规嵁涔愬彞杩涘害鍜岃鑹诧紝璋冩暣鍔涘害鍜岃妭濂忓瘑搴?
                    phrase_progress = phrase_plan.phrase_progress_at_bar(bar_idx, phrase_idx)
                    
                    # 鑺傚绉疮锛氫箰鍙ュ墠鍗婃閫愭笎澧炲己锛屽悗鍗婃閲婃斁
                    if phrase_progress < 0.5:
                        # 绉疮闃舵锛氶€愭笎澧炲己
                        rhythm_intensity = 0.7 + phrase_progress * 0.3
                    else:
                        # 閲婃斁闃舵锛氫繚鎸佹垨鐣ュ井鍑忓急
                        rhythm_intensity = 1.0 - (phrase_progress - 0.5) * 0.2
                    
                    # 鏍规嵁鑺傚寮哄害鍜屽己鎷嶅急鎷嶈绠楀熀纭€鍔涘害
                    if is_strong_beat:
                        base_velocity = int(100 + 20 * rhythm_intensity)
                    else:
                        base_velocity = int(80 + 15 * rhythm_intensity * melody_rng.random())

                    if style == SeedMusicStyle.BATTLE:
                        # 鎴樻枟锛氫富鏃嬪緥鏁翠綋鏇寸獊鍑轰竴浜涳紱鍙樹綋鍙啀寰皟
                        if is_battle_melody:
                            base_velocity = min(127, int(base_velocity * 1.35))
                        elif is_battle_drums:
                            base_velocity = min(127, int(base_velocity * 1.1))
                        else:
                            base_velocity = min(127, int(base_velocity * 1.2))
                    elif style == SeedMusicStyle.SUSPENSE:
                        # 鎮枒锛氫富鏃嬪緥鏃㈣鍔ㄦ€佽捣浼忥紝鍙堣鍘嬭繃鑳屾櫙
                        jitter = int(melody_rng.uniform(-10, 10))
                        base_velocity = max(55, min(127, int(base_velocity * 1.15) + jitter))
                    elif style == SeedMusicStyle.CALM:
                        # 鑸掔紦锛氭暣浣撳姏搴︽洿鏌斿拰
                        base_velocity = int(base_velocity * 0.8)
                    elif style == SeedMusicStyle.ROCK:
                        # 鎽囨粴锛氫富鏃嬪緥鍔涘害杈冨己锛屼絾涓嶈繃浜庣獊鍑猴紙鍥犱负瑕佺獊鍑洪紦鐐癸級
                        base_velocity = min(127, int(base_velocity * 1.1))

                    # Intro娈靛凡缁忓湪鍓嶉潰鍗曠嫭澶勭悊锛岃繖閲屼笉闇€瑕佸啀澶勭悊

                    if style == SeedMusicStyle.BATTLE and dur_beats >= 0.5:
                        # 鎴樻枟椋庢牸锛氬悓涓€鏍煎瓙閲屾妸闊崇鍒囨垚涓ゆ鐭績瑙﹀彂锛岃惀閫犵揣寮犳劅
                        sub_beats = dur_beats / 2.0
                        sub_time = sub_beats * beat_duration
                        # 鍗曟瑙﹀彂鐨勫疄闄呮寔缁椂闂存洿鐭竴浜?
                        duration_beats_for_time = max(0.25, sub_beats * 0.5)
                        duration = duration_beats_for_time * beat_duration

                        for rep in range(2):
                            rep_start = start_time + rep * sub_time
                            velocity = base_velocity + (5 if rep == 1 else 0)  # 绗簩涓嬬暐寰洿閲嶄竴鐐?
                            note = Note(
                                pitch=pitch,
                                start_time=rep_start,
                                duration=duration,
                                velocity=velocity,
                                waveform=style_params.melody_waveform,
                                duty_cycle=style_params.melody_duty,
                                adsr=melody_adsr,
                            )
                            melody_track.notes.append(note)
                    else:
                        # 鍏朵粬椋庢牸锛氭寜鐓ф甯歌妭鎷嶉暱搴︾敓鎴愪竴涓煶锛屼絾鍙寜椋庢牸寰皟鏃跺€煎拰闊崇鏁伴噺
                        if style == SeedMusicStyle.SUSPENSE and dur_beats >= 0.5:
                            # 鎮枒锛氬湪褰撳墠鑺傛媿鏍煎瓙鍐呮墦涓夎繛鍑伙紝鍚屾椂淇濊瘉鏁存牸鍑犱箮琚～婊★紝閬垮厤"涓€娈典竴娈垫柇鎺?鐨勬劅瑙?
                            sub_beats = dur_beats / 3.0
                            sub_time = sub_beats * beat_duration
                            # 鍓嶄袱涓嬬暐鐭紝鏈€鍚庝竴涓嬬暐闀匡紝涓夎€呭悎璧锋潵鍩烘湰瑕嗙洊鏁存牸
                            sub_durations = [
                                max(0.18 * beat_duration, sub_time * 0.75),
                                max(0.18 * beat_duration, sub_time * 0.8),
                                max(0.25 * beat_duration, sub_time * 1.0),
                            ]

                            current_start = start_time
                            for i in range(3):
                                # 涓棿閭ｄ釜鐣ラ噸锛屽墠鍚庣暐杞伙紝褰㈡垚銆屽急-寮?寮便€嶇殑鎯婃倸寰嬪姩
                                if i == 1:
                                    vel = min(127, int(base_velocity * 1.05))
                                else:
                                    vel = max(50, int(base_velocity * 0.9))
                                note = Note(
                                    pitch=pitch,
                                    start_time=current_start,
                                    duration=sub_durations[i],
                                    velocity=vel,
                                    waveform=style_params.melody_waveform,
                                    duty_cycle=style_params.melody_duty,
                                    adsr=melody_adsr,
                                )
                                melody_track.notes.append(note)
                                # 涓嬩竴娆＄殑璧风偣绱ц窡涓婁竴闊崇粨鏉燂紝鍑忓皯绌虹櫧
                                current_start += sub_time
                        else:
                            if style == SeedMusicStyle.CALM:
                                # 鑸掔紦锛氱暐寰媺闀块煶绗︼紝璁╁彞瀛愭洿杩炶疮
                                duration_beats_for_time = dur_beats * 1.1
                            else:
                                duration_beats_for_time = dur_beats
                            duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)

                            # 鍦ㄥ己鎷嶄笂娣诲姞鍙犻煶锛堝舰鎴愬拰寮︽劅锛?
                            will_add_overlay = is_strong_beat and melody_rng.random() < 0.4  # 40%姒傜巼娣诲姞鍙犻煶
                            
                            # 濡傛灉鏈夊彔闊筹紝闄嶄綆涓婚煶鍔涘害锛岄伩鍏嶅彔鍔犲悗闊抽噺绐佺劧澧炲ぇ
                            if will_add_overlay:
                                # 涓婚煶鍔涘害闄嶄綆鍒?0%锛屼负鍙犻煶鐣欏嚭绌洪棿
                                adjusted_velocity = max(60, int(base_velocity * 0.7))
                            else:
                                adjusted_velocity = base_velocity
                            
                            note = Note(
                                pitch=pitch,
                                start_time=start_time,
                                duration=duration,
                                velocity=adjusted_velocity,
                                waveform=style_params.melody_waveform,
                                duty_cycle=style_params.melody_duty,
                                adsr=melody_adsr,
                            )
                            melody_track.notes.append(note)
                            
                            # 娣诲姞鍙犻煶
                            if will_add_overlay:
                                # 閫夋嫨娣诲姞涓夊害鎴栦簲搴﹀彔闊?
                                overlay_choice = melody_rng.choice(["third", "fifth"])
                                if overlay_choice == "third":
                                    # 娣诲姞涓夊害锛?2涓害鏁帮級
                                    overlay_degree = degree_clamped + 2
                                else:
                                    # 娣诲姞浜斿害锛?4涓害鏁帮級
                                    overlay_degree = degree_clamped + 4
                                
                                # 纭繚搴︽暟鍦ㄦ湁鏁堣寖鍥村唴
                                overlay_degree = max(0, min(overlay_degree, len(scale_offsets) - 1))
                                overlay_pitch = root_midi + scale_offsets[overlay_degree]
                                overlay_pitch = max(pitch_min, min(overlay_pitch, pitch_max))
                                
                                # 鍙犻煶鐨勫姏搴﹁涓哄師涓婚煶鐨?0%锛屼笌闄嶄綆鍚庣殑涓婚煶鍙犲姞鍚庢€婚煶閲忕害绛変簬鍘熶富闊崇殑85%
                                overlay_velocity = max(50, int(base_velocity * 0.5))
                                
                                overlay_note = Note(
                                    pitch=overlay_pitch,
                                    start_time=start_time,
                                    duration=duration * 0.8,  # 鍙犻煶绋嶇煭涓€浜?
                                    velocity=overlay_velocity,
                                    waveform=style_params.melody_waveform,
                                    duty_cycle=style_params.melody_duty,
                                    adsr=melody_adsr,
                                )
                                melody_track.notes.append(overlay_note)

                    beat_in_bar += dur_beats
                # 濡傛灉motif鎬绘椂闀垮皬浜庡皬鑺傞暱搴︼紝涓旇繕娌℃湁濉弧灏忚妭锛岀户缁噸澶?
                if motif_total_beats < beats_per_bar and beat_in_bar < beats_per_bar - 1e-6:
                    # 缁х画寰幆锛岄噸澶峬otif
                    continue
                else:
                    # motif宸茬粡濉弧鎴栬秴杩囧皬鑺傞暱搴︼紝閫€鍑?
                    break

    # 瀵圭粨灏惧仛涓€涓畝鍗曠殑銆岀粓姝㈠紡銆嶅鐞嗭細纭繚鏈€鍚庝竴涓煶钀藉湪涓诲拰寮︿笂骞剁◢闀夸竴鐐?
    if melody_track.notes:
        last_note = melody_track.notes[-1]
        tonic_pitch = root_midi + scale_offsets[chord_root_degree(1)]
        # 濡傛灉鏈€鍚庝竴涓煶涓嶆槸涓婚煶闄勮繎锛屽垯寮哄埗闈犺繎涓婚煶
        if abs(last_note.pitch - tonic_pitch) > 2:
            last_note.pitch = tonic_pitch
        # 寤堕暱鏈€鍚庝竴涓煶鍒版洸瀛愮粨鏉熺殑 1 灏忚妭鍐咃紙涓嶆敼鎬婚暱搴︼紝鍙媺闀垮熬闊筹級
        song_end_time = total_beats * beat_duration
        desired_end = song_end_time
        last_note.duration = max(last_note.duration, desired_end - last_note.start_time)

    project.add_track(melody_track)

    track_build_context = TrackBuildContext(
        bass_rng=bass_rng,
        harmony_rng=harmony_rng,
        drum_rng=drum_rng,
        style=style,
        variant_id=variant_id,
        style_params=style_params,
        style_config=style_config,
        phrase_plan=phrase_plan,
        length_bars=length_bars,
        beats_per_bar=beats_per_bar,
        beat_duration=beat_duration,
        bars_progression=tuple(bars_progression),
        root_midi=root_midi,
        scale_offsets=tuple(scale_offsets),
        quiet_bars=quiet_bars,
        dance_harmony_start_bar=dance_harmony_start_bar,
        drum_density=drum_density,
    )

    bass_track = build_bass_track(track_build_context, enable_bass=enable_bass)

    style_config.apply_melody_effects(melody_track)

    if bass_track is not None:
        project.add_track(bass_track)

    harmony_track = build_harmony_track(track_build_context, enable_harmony=enable_harmony)

    volumes = style_config.get_track_volumes(variant_id)
    melody_track.volume = volumes["melody"]
    if bass_track is not None:
        bass_track.volume = volumes["bass"]
    if harmony_track is not None:
        harmony_track.volume = volumes["harmony"]
    drum_boost = volumes["drum_boost"]

    if harmony_track is not None:
        project.add_track(harmony_track)

    drum_track = build_drum_track(
        track_build_context,
        drum_boost=drum_boost,
        enable_drums=enable_drums,
    )
    if drum_track is not None:
        project.add_track(drum_track)

    return project

