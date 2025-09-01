import math, time, queue
from win32com.client import Dispatch, GetActiveObject

PROGID = "UCwinRoad.F8ApplicationServicesProxy"
CAL_GAIN = 0.050  # 평가용 계산에 쓰는 기본 게인 (컨트롤에서 보정되는 값 아님)
TYPE_TO_KEYWORD = {"A": "typeA", "B": "typeB", "C": "typeC"}

def attach():
    try:
        return GetActiveObject(PROGID)
    except:
        return Dispatch(PROGID)

def safe_get(o, n):
    try:
        return getattr(o, n)
    except:
        return None

def try_vec3(v):
    for names in (("X","Y","Z"),("x","y","z")):
        if all(hasattr(v, n) for n in names):
            try:
                return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
            except:
                pass
    for names in (("X","Y","Z"),("x","y","z")):
        if all(hasattr(v, n) and callable(getattr(v, n)) for n in names):
            try:
                return float(getattr(v, names[0])()), float(getattr(v, names[1])()), float(getattr(v, names[2])())
            except:
                pass
    return None

def _get_bounding_box(inst):
    f = safe_get(inst, "BoundingBox")
    if callable(f):
        try:
            return f(0)
        except:
            pass
        try:
            return f()
        except:
            pass
    return None

def _axis_len(bb, axis_name):
    ax = safe_get(bb, axis_name)
    if ax is None and callable(safe_get(bb, axis_name)):
        ax = safe_get(bb, axis_name)()
    vec = try_vec3(ax) if ax is not None else None
    if not vec:
        return None
    x, y, z = vec
    return (x * x + y * y + z * z) ** 0.5

def _get_scale(inst):
    try:
        s = float(safe_get(inst, "Scale")) if safe_get(inst, "Scale") is not None else 1.0
    except:
        s = 1.0
    sf = safe_get(inst, "ScaleFactor")
    v = try_vec3(sf) if sf is not None else None
    if not v:
        v = (1.0, 1.0, 1.0)
    return s, v  # (scalar, (sx,sy,sz))

def _scan_type_size_once(proj, keyword):
    try:
        n = proj.ThreeDModelInstancesCount
    except:
        return None, None
    best = None
    for i in range(n):
        inst = proj.ThreeDModelInstance(i)
        name = safe_get(inst, "Name") or ""
        if keyword.lower() not in name.lower():
            continue
        bb = _get_bounding_box(inst)
        if bb is None:
            continue
        ly = _axis_len(bb, "yAxis")
        lz = _axis_len(bb, "zAxis")
        if ly is None or lz is None:
            continue
        size_y = 2.0 * ly
        size_z = 2.0 * lz
        sc, (sx, sy, sz) = _get_scale(inst)
        size_y *= (sc * sy)
        size_z *= (sc * sz)
        if 0.03 <= size_y <= 0.40 and 2.0 <= size_z <= 5.0:
            score = 0.0
            score -= abs(size_z - 3.5) * 10.0
            score -= max(0.0, size_y - 0.35) * 50.0
            if (best is None) or (score > best[0]):
                best = (score, round(size_y, 6), round(size_z, 6))
    return (best[1], best[2]) if best else (None, None)

def read_gt_size_now(proj, type_letter, attempts=6, sleep_sec=0.25):
    keyword = TYPE_TO_KEYWORD.get(type_letter)
    if not keyword:
        return None, None
    for _ in range(attempts):
        h, z = _scan_type_size_once(proj, keyword)
        if (h is not None) and (z is not None):
            return h, z
        time.sleep(sleep_sec)
    return None, None

def compute_rms(v_kmh, h_m, L_m):
    if not h_m or not L_m or h_m <= 0 or L_m <= 0:
        return None
    v = v_kmh / 3.6
    term1 = CAL_GAIN * (1.0 / math.sqrt(2.0)) * h_m
    term2 = (v * math.pi / L_m) ** 2
    return term1 * term2

def classify_rms(rms):
    if rms < 0.315:
        return "매우 쾌적함"
    if rms < 0.5:
        return "쾌적함"
    if rms < 0.8:
        return "보통"
    if rms < 1.25:
        return "불쾌함"
    return "매우 불쾌함"

# ================== 평가 노드 ==================
def run_evaluate_node(vision_to_eval_queue, control_to_eval_queue, eval_to_control_queue):
    app = attach()
    proj = app.Project
    current_type = None

    while True:
        # Vision → Evaluate: type 최신화
        try:
            vmsg = vision_to_eval_queue.get_nowait()
            if "type" in vmsg:
                current_type = vmsg["type"]
        except queue.Empty:
            pass

        # Control → Evaluate: tS, eR 수신
        try:
            msg = control_to_eval_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if msg.get("msg") != "control" or not current_type:
            continue

        base_tS = msg.get("tS")
        base_eR = msg.get("eR")

        # GT 실제 사이즈 읽기
        h, z = read_gt_size_now(proj, current_type)
        if h is None or z is None:
            continue

        # 충돌 시 실제 속도 rS
        try:
            rS = float(app.SimulationCore.TrafficSimulation.Driver.CurrentCar.Speed(1))
        except:
            rS = float(app.SimulationCore.TrafficSimulation.Driver.CurrentCar.Speed()) * 3.6

        # 실제 RMS
        tR = compute_rms(rS, h, z)
        if not tR:
            continue
        comfort = classify_rms(tR)

        # 로그 출력 (항상)
        print(f"[Evaluate] rS:{rS:.1f}km/h | tR:{tR:.2f} | 승차감:{comfort}")

        # 모든 경우에 보정 계수 산출 및 전송
        cal_gain_scale = (tR / base_eR) if (base_eR and base_eR > 0) else 1.0
        pwm_weight     = (base_tS / rS) if (rS and rS > 0) else 1.0

        eval_to_control_queue.put({
            "msg": "evaluate",
            "CAL_GAIN": cal_gain_scale,
            "PWM_WEIGHT": pwm_weight
        })
