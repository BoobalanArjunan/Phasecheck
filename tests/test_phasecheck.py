import csv
import json

import numpy as np
import pytest
import soundfile as sf

import phasecheck.check as chk
import synth
from conftest import pair, sound, write
from phasecheck.analysis import LOSS_CAP_DB, PhaseResult, analyse, load_stereo
from phasecheck.check import FAKE, LIMITED, OK, SKIPPED, UNSURE, Verdict, check_file, judge
from phasecheck.cli import find_audio, main
from phasecheck.report import summary_line, text, to_dict, to_json, write_csv

SR = 44100


def res(left, right, sr=SR):
    return analyse(synth.to_pcm16(left).astype(float) / 32767, synth.to_pcm16(right).astype(float) / 32767, sr)


def rot(degrees, sr=SR, seed=0):
    """The sound and the same sound shifted by a fixed phase angle (see synth.rotate)."""
    x = sound(sr, seed)
    return x, synth.rotate(x, degrees)


def expected_loss(degrees):
    return -10 * np.log10((1 + np.cos(np.deg2rad(degrees))) / 2)


# ---------------------------------------------------------------- the basic relationships
def test_identical_channels_lose_nothing_and_are_dual_mono():
    x = sound(SR)
    r = res(x, x)
    assert r.loss_db < 0.2 and r.correlation > 0.999 and r.dual_mono
    v = judge(r, "a.wav", SR)
    assert v.status == OK and v.dual_mono and "mono stored as stereo" in v.reason


def test_channels_a_quarter_turn_apart_lose_3_db_and_pass():
    r = res(*rot(90))
    assert abs(r.loss_db - 3.01) < 0.3 and abs(r.correlation) < 0.05 and not r.dual_mono
    assert judge(r, "a.wav", SR).status == OK


def test_independent_noise_channels_pass():
    """Real stereo is somewhere between identical and unrelated; unrelated channels lose about 2-4 dB."""
    r = res(sound(SR, 0), sound(SR, 1))
    assert 1.0 < r.loss_db < 5.0 and not r.dual_mono
    assert judge(r, "a.wav", SR).status == OK


def test_inverted_channels_fail_with_a_large_loss():
    x = sound(SR)
    r = res(x, -x)
    assert r.loss_db >= 40 and r.correlation < -0.99
    v = judge(r, "a.wav", SR)
    assert v.status == FAKE and v.level == "FAIL" and "opposite in phase" in v.reason


def test_the_loss_is_capped():
    x = sound(SR)
    assert res(x, -x).loss_db <= LOSS_CAP_DB


def test_a_quieter_right_channel_in_phase_is_fine_and_not_dual_mono():
    x = sound(SR)
    r = res(x, 0.5 * x)
    assert r.loss_db < 1.0 and r.correlation > 0.999 and not r.dual_mono
    assert judge(r, "a.wav", SR).status == OK


def test_partly_out_of_phase_channels_warn():
    r = res(*rot(130))                            # 7.5 dB
    assert abs(r.loss_db - expected_loss(130)) < 0.4 and 6 <= r.loss_db < 10
    v = judge(r, "a.wav", SR)
    assert v.status == LIMITED and v.level == "WARN" and "partly out of phase" in v.reason


def test_strongly_out_of_phase_channels_fail():
    r = res(*rot(160))                            # 15 dB
    assert abs(r.loss_db - expected_loss(160)) < 1.0 and r.loss_db >= 10
    assert judge(r, "a.wav", SR).status == FAKE


def test_correlation_sign_follows_the_phase():
    x = sound(SR)
    assert res(x, x).correlation > 0.99 and res(x, -x).correlation < -0.99
    assert abs(res(*rot(90)).correlation) < 0.05
    assert res(*rot(60)).correlation > 0.4 and res(*rot(120)).correlation < -0.4


# ---------------------------------------------------------------- one band out of phase
def band_flipped(lo, hi, sr=SR):
    x = sound(sr)
    return x, x - 2 * synth.band(x, sr, lo, hi)


def test_a_band_inverted_in_one_channel_is_found_by_its_band():
    x, y = band_flipped(2000, 8000)
    r = res(x, y)
    assert r.band_loss_db["2-8 kHz"] is not None and r.band_loss_db["2-8 kHz"] >= 10
    v = judge(r, "a.wav", SR)
    assert v.status in (LIMITED, FAKE) and v.worst_band == "2-8 kHz"


def test_a_band_holding_almost_no_energy_is_ignored():
    """The sound ends at 5 kHz; a trace of sound above 8 kHz (under 1% of the energy) is inverted in one channel."""
    low = synth.band(sound(SR, 0), SR, 100, 5000)
    trace = 0.01 * synth.band(sound(SR, 1), SR, 9000, 15000)
    r = res(low + trace, low - trace)
    assert r.band_loss_db["above 8 kHz"] is None
    assert judge(r, "a.wav", SR).status == OK


def test_the_same_trace_counts_when_it_holds_enough_energy():
    low = synth.band(sound(SR, 0), SR, 100, 5000)
    trace = 0.5 * synth.band(sound(SR, 1), SR, 9000, 15000)
    r = res(low + trace, low - trace)
    assert r.band_loss_db["above 8 kHz"] is not None and r.band_loss_db["above 8 kHz"] >= 10
    assert judge(r, "a.wav", SR).status == LIMITED


def test_band_rule_warns_when_the_whole_file_does_not_cancel():
    x, y = band_flipped(2000, 8000)
    r = res(x, y)
    assert r.loss_db < chk.WARN_DB                          # the file as a whole is fine
    v = judge(r, "a.wav", SR)
    assert v.status == LIMITED and "band cancels" in v.reason


def test_bands_that_do_not_exist_at_a_low_sample_rate_are_none():
    r = res(sound(16000), sound(16000, 1), 16000)
    assert r.band_loss_db["above 8 kHz"] is None


# ---------------------------------------------------------------- only the loud parts count
def test_a_quiet_inverted_passage_is_ignored():
    x = sound(SR, 0, 8.0)
    half = len(x) // 2
    left = x
    right = np.concatenate([x[:half], -x[half:] * 0.003])   # second half inverted but about 50 dB quieter
    left = np.concatenate([x[:half], x[half:] * 0.003])
    r = res(left, right)
    assert r.loss_db < 1.0
    assert judge(r, "a.wav", SR).status == OK


def test_a_loud_inverted_passage_counts_but_is_averaged_into_the_file():
    """Known limit: a passage that cancels completely only costs the file as a whole its share of the energy, so it can pass."""
    x = sound(SR, 0, 8.0)
    half = len(x) // 2
    right = np.concatenate([x[:half], -x[half:]])
    r = res(x, right)
    kept = float(np.sum(x[:half] ** 2) / np.sum(x ** 2))              # share of the energy that stays in phase
    assert abs(r.loss_db - (-10 * np.log10(kept))) < 0.4
    assert 1.0 < r.loss_db < 6.0
    assert judge(r, "a.wav", SR).status == OK


def test_a_long_file_is_judged_by_its_middle(tmp_path):
    x = sound(SR, 0, 12.0)
    third = len(x) // 3
    right = np.concatenate([-x[:third], x[third:2 * third], -x[2 * third:]])
    p = write(tmp_path / "long.wav", pair(x, right), SR)
    data, sr = load_stereo(p, max_seconds=4)
    assert data.shape[0] == 4 * SR
    r = analyse(data[:, 0], data[:, 1], sr)
    assert r.loss_db < 0.3                                   # the in-phase middle, not the inverted ends


# ---------------------------------------------------------------- files that cannot be judged
def test_a_silent_channel_is_not_a_phase_problem(tmp_path):
    x = sound(SR)
    v = check_file(write(tmp_path / "s.wav", pair(x, np.zeros_like(x)), SR))
    assert v.status == UNSURE and "silent" in v.reason and "right" in v.reason
    v = check_file(write(tmp_path / "s2.wav", pair(np.zeros_like(x), x), SR))
    assert v.status == UNSURE and "left" in v.reason


def test_a_mono_file_is_skipped(tmp_path):
    v = check_file(write(tmp_path / "m.wav", sound(SR), SR))
    assert v.status == SKIPPED and v.level == "SKIP" and v.channels == 1


def test_a_file_with_more_than_two_channels_is_skipped(tmp_path):
    x = sound(SR)
    p = tmp_path / "q.wav"
    sf.write(str(p), synth.to_pcm16(np.stack([x, x, x], axis=1)), SR, subtype="PCM_16")
    v = check_file(p)
    assert v.status == SKIPPED and v.channels == 3 and "3 channels" in v.reason


def test_a_short_file_needs_a_look(tmp_path):
    x = sound(SR, 0, 1.0)
    assert check_file(write(tmp_path / "s.wav", pair(x, -x), SR)).status == UNSURE


def test_an_all_silent_file_needs_a_look(tmp_path):
    z = np.zeros(SR * 4)
    assert check_file(write(tmp_path / "z.wav", pair(z, z), SR)).status == UNSURE


def test_an_unreadable_file_is_an_error(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_bytes(b"not audio")
    v = check_file(p)
    assert v.status == chk.ERROR and v.level == "ERROR" and "could not read" in v.reason


def test_judge_of_nothing_needs_a_look():
    assert judge(None, "a.wav", SR).status == UNSURE


# ---------------------------------------------------------------- thresholds
def test_thresholds_can_be_changed():
    r = res(*rot(130))                                      # 7.5 dB
    assert judge(r, "a", SR).status == LIMITED
    assert judge(r, "a", SR, warn_db=8.5, fail_db=12).status == OK
    assert judge(r, "a", SR, warn_db=3, fail_db=7).status == FAKE


def test_defaults_are_the_documented_values():
    assert (chk.WARN_DB, chk.FAIL_DB, chk.BAND_FAIL_DB) == (6.0, 10.0, 10.0)


# ---------------------------------------------------------------- sample rates
@pytest.mark.parametrize("sr", [16000, 22050, 48000])
def test_the_same_relationship_gives_the_same_loss_at_every_rate(sr):
    x = sound(sr)
    assert res(x, x, sr).dual_mono
    assert res(x, -x, sr).loss_db >= 40
    assert abs(res(x, synth.rotate(x, 90), sr).loss_db - 3.01) < 0.3


# ---------------------------------------------------------------- reports
def test_csv_columns_and_values(tmp_path):
    out = tmp_path / "v.csv"
    write_csv(out, [Verdict("a.wav", 44100, 2, FAKE, "r", 31.2, -0.98, "2-8 kHz", 40.0, False, 7.0)])
    row = list(csv.DictReader(open(out, encoding="utf-8")))[0]
    assert list(row) == ["file", "sample_rate", "channels", "verdict", "reason", "downmix_loss_db", "correlation", "worst_band",
                         "worst_band_loss_db", "dual_mono", "seconds_analysed"]
    assert (row["verdict"], row["downmix_loss_db"], row["correlation"], row["worst_band"], row["channels"]) == ("FAIL", "31.2", "-0.98", "2-8 kHz", "2")


def test_json_report_has_the_summary_and_every_file():
    vs = [Verdict("a.wav", 44100, 2, FAKE, "r", 31.2, -0.98),
          Verdict("b.wav", 44100, 2, OK, "ok", 3.0, 0.0),
          Verdict("m.wav", 44100, 1, SKIPPED, "mono")]
    d = to_dict(vs)
    assert d["tool"] == "phasecheck" and d["version"] and "alpha" in d["evidence"]
    assert d["summary"] == {"files": 3, "PASS": 1, "WARN": 0, "FAIL": 1, "REVIEW": 0, "SKIP": 1, "ERROR": 0}
    a = d["files"][0]
    assert (a["file"], a["verdict"], a["downmix_loss_db"], a["correlation"], a["channels"]) == ("a.wav", "FAIL", 31.2, -0.98, 2)
    assert json.loads(to_json(vs))["summary"]["files"] == 3


def test_text_report_hides_pass_and_skip_unless_asked():
    vs = [Verdict("a.wav", 44100, 2, FAKE, "r"), Verdict("b.wav", 44100, 2, OK, "ok"), Verdict("m.wav", 44100, 1, SKIPPED, "mono")]
    t = text(vs)
    assert "a.wav" in t and "b.wav" not in t and "m.wav" not in t
    t2 = text(vs, show_pass=True)
    assert "b.wav" in t2 and "m.wav" in t2
    assert "1 pass" in summary_line(vs) and "1 skipped" in summary_line(vs) and "1 fail" in summary_line(vs)


# ---------------------------------------------------------------- command line
def make_folder(tmp_path):
    x = sound(SR)
    write(tmp_path / "good.wav", pair(sound(SR, 0), sound(SR, 1)), SR)
    write(tmp_path / "bad.wav", pair(x, -x), SR)
    (tmp_path / "sub").mkdir()
    write(tmp_path / "sub" / "mono.wav", x, SR)
    return tmp_path


def test_find_audio_walks_folders_and_skips_junk(tmp_path):
    make_folder(tmp_path)
    (tmp_path / "._hidden.wav").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    names = [p.name for p in find_audio(tmp_path)]
    assert names == ["bad.wav", "good.wav", "mono.wav"]


def test_cli_exit_code_is_1_when_something_fails(tmp_path, capsys):
    make_folder(tmp_path)
    assert main(["check", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "bad.wav" in out and "good.wav" not in out


def test_cli_exit_code_is_0_when_nothing_fails(tmp_path, capsys):
    write(tmp_path / "good.wav", pair(sound(SR, 0), sound(SR, 1)), SR)
    assert main(["check", str(tmp_path)]) == 0


def test_cli_json_prints_valid_json(tmp_path, capsys):
    make_folder(tmp_path)
    rc = main(["check", str(tmp_path), "--json"])
    d = json.loads(capsys.readouterr().out)
    assert rc == 1 and d["summary"]["files"] == 3
    assert (d["summary"]["PASS"], d["summary"]["FAIL"], d["summary"]["SKIP"]) == (1, 1, 1)


def test_cli_writes_csv(tmp_path):
    make_folder(tmp_path)
    out = tmp_path / "v.csv"
    main(["check", str(tmp_path), "--out", str(out)])
    assert len(list(csv.DictReader(open(out, encoding="utf-8")))) == 3


def test_cli_threshold_options_change_the_verdict(tmp_path, capsys):
    write(tmp_path / "p.wav", pair(*rot(130)), SR)
    assert main(["check", str(tmp_path)]) == 0                                   # WARN only
    assert main(["check", str(tmp_path), "--fail-db", "7", "--warn-db", "3"]) == 1


def test_cli_rejects_warn_above_fail(tmp_path, capsys):
    make_folder(tmp_path)
    assert main(["check", str(tmp_path), "--warn-db", "12", "--fail-db", "8"]) == 2


def test_cli_missing_path_and_empty_folder(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope")]) == 2
    assert main(["check", str(tmp_path)]) == 2


def test_cli_parallel_jobs_same_result(tmp_path, capsys):
    make_folder(tmp_path)
    main(["check", str(tmp_path), "--json"])
    a = json.loads(capsys.readouterr().out)
    main(["check", str(tmp_path), "--json", "--jobs", "2"])
    b = json.loads(capsys.readouterr().out)
    assert a["summary"] == b["summary"] and [f["file"] for f in a["files"]] == [f["file"] for f in b["files"]]


def test_cli_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "phasecheck 0.1.0a1" in capsys.readouterr().out


# ---------------------------------------------------------------- the limits themselves (judge on a hand-made measurement)
def made(loss, corr=0.0, bands=None, dual=False, silent=None):
    return PhaseResult(SR, 8.0, 8.0, loss, corr, bands or {"20-250 Hz": 3.0, "250 Hz-2 kHz": 3.0, "2-8 kHz": 3.0, "above 8 kHz": 3.0}, dual, silent)


@pytest.mark.parametrize("loss,expected", [(5.99, OK), (6.0, LIMITED), (9.99, LIMITED), (10.0, FAKE), (30.0, FAKE)])
def test_full_band_limits_are_at_6_and_10_db(loss, expected):
    assert judge(made(loss), "a", SR).status == expected


@pytest.mark.parametrize("band_loss,expected", [(9.99, OK), (10.0, LIMITED), (25.0, LIMITED)])
def test_band_limit_is_10_db(band_loss, expected):
    v = judge(made(3.0, bands={"20-250 Hz": 3.0, "250 Hz-2 kHz": band_loss, "2-8 kHz": 3.0, "above 8 kHz": None}), "a", SR)
    assert v.status == expected
    if expected == LIMITED:
        assert v.worst_band == "250 Hz-2 kHz" and v.worst_band_loss_db == band_loss


def test_the_worst_band_is_the_one_with_the_largest_loss():
    v = judge(made(3.0, bands={"20-250 Hz": 2.0, "250 Hz-2 kHz": 4.0, "2-8 kHz": 9.0, "above 8 kHz": 6.0}), "a", SR)
    assert v.worst_band == "2-8 kHz" and v.worst_band_loss_db == 9.0


def test_a_correlation_below_minus_half_is_called_opposite_in_phase():
    assert "opposite in phase" in judge(made(12.0, corr=-0.5), "a", SR).reason
    assert "opposite in phase" not in judge(made(12.0, corr=-0.49), "a", SR).reason


def test_a_silent_channel_wins_over_everything_else():
    v = judge(made(60.0, corr=-1.0, silent=1), "a", SR)
    assert v.status == UNSURE


def test_dual_mono_wins_over_the_loss_rules():
    assert judge(made(0.0, corr=1.0, dual=True), "a", SR).status == OK


def test_verdict_levels_and_fraction_free_properties():
    assert [Verdict("a", 1, 2, s, "").level for s in (OK, LIMITED, FAKE, UNSURE, SKIPPED, chk.ERROR)] == ["PASS", "WARN", "FAIL", "REVIEW", "SKIP", "ERROR"]


# ---------------------------------------------------------------- planted-bug follow-ups
def test_a_level_difference_of_nearly_a_decibel_is_not_dual_mono():
    x = sound(SR)
    r = res(x, 0.9 * x)            # right is 0.9 dB quieter: in phase, loses nothing, but not identical
    assert r.loss_db < 0.2 and r.correlation > 0.9999
    assert not r.dual_mono
    assert res(x, 0.97 * x).dual_mono   # 0.26 dB apart still counts as identical


def test_only_the_loud_part_counts_as_active_time():
    x = sound(SR, seconds=8.0)
    half = len(x) // 2
    y = x.copy()
    y[half:] *= 10 ** (-50 / 20)   # second half 50 dB quieter, below the loud-frame floor
    r = res(y, y)
    assert 3.0 < r.active_seconds < 4.5
    assert res(x, x).active_seconds > 7.0
