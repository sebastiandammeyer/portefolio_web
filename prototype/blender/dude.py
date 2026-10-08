"""Sebastian-rytteren: tager Poly Pizza-manden (Business Dude), laver ham om og giver ham et skelet.

Kør:  Blender -b --python dude.py -- <sti til Business Dude.glb> <mappe til resultat>
Resultat: sebastian.glb (med skelet og tekstur) og sebastian_preview_*.png

Ændringer i forhold til originalen:
 - lyst, mellemlangt hår (nye hårstykker bag og ved siden af hovedet)
 - fuldskæg fjernet, så ansigtet er glatbarberet; sur mund vendt til smil
 - blå øjne, briller
 - skjorte og slips i stedet for jakkesæt
 - skelet (hofte, ryg, hoved, arme, hænder, ben, fødder) med vægte
"""
import bpy, bmesh, sys, math
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = argv[0], argv[1]
S = 0.85   # skala fra originalen (4.57 høj) til cykel-enheder

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
# bag skalaen ind i mesh og fjern rod-noden
bpy.context.view_layer.objects.active = obj
obj.parent = None
bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.data.objects):
    if o.type == 'EMPTY': bpy.data.objects.remove(o)
if obj.data.shape_keys: obj.shape_key_clear()   # importen lægger en basisform på, som ellers overskriver ændringerne

# ---- tekstur ----
img = [i for i in bpy.data.images if i.size[0] > 0][0]
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)    # rækker nedefra (v=0 nederst)
def tex_rgb(x, y):          # pixel i billedets egne koordinater (y fra toppen)
    return px[H - 1 - y, x, :3].copy()

def uv_to_px(u, v):
    return u * W, (1 - v) * H

def fill_tris(mask, tris):
    for (a, b, c) in tris:
        xs = [a[0], b[0], c[0]]; ys = [a[1], b[1], c[1]]
        x0, x1 = int(max(min(xs), 0)), int(min(max(xs), W - 1)); y0, y1 = int(max(min(ys), 0)), int(min(max(ys), H - 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-9: continue
        l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
        l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= -.02) & (l2 >= -.02) & (l3 >= -.02)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside

# ---- opdel i løse dele og klassificér (originalens koordinater: x frem, y sidelæns, z op) ----
bm = bmesh.new(); bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
uvl = bm.loops.layers.uv.active
UVNAME = obj.data.uv_layers.active.name
seen = set(); parts = []
for v0 in bm.verts:
    if v0.index in seen: continue
    st = [v0]; seen.add(v0.index); comp = []
    while st:
        x = st.pop(); comp.append(x)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen: seen.add(y.index); st.append(y)
    idx = {c.index for c in comp}
    cs = [c.co for c in comp]
    mn = Vector([min(c[i] for c in cs) for i in range(3)]); mx = Vector([max(c[i] for c in cs) for i in range(3)])
    faces = [f for f in bm.faces if f.verts[0].index in idx]
    us = [l[uvl].uv for f in faces for l in f.loops]
    uc = (sum(u.x for u in us) / len(us) * W, (1 - sum(u.y for u in us) / len(us)) * H)
    parts.append(dict(verts=idx, faces=faces, mn=mn, mx=mx, c=(mn + mx) / 2, n=len(comp), uc=uc))

def near(p, x, y, r=14): return abs(p['uc'][0] - x) < r and abs(p['uc'][1] - y) < r

for p in parts:
    c, mn, mx = p['c'], p['mn'], p['mx']
    p['kind'] = 'torso'
    if c.z > 3.75: p['kind'] = 'head'
    elif abs(c.y) > .6 and 3.0 < c.z < 3.7: p['kind'] = 'hand' if abs(c.y) > 1.7 and p['n'] > 40 and False else 'arm'
    elif c.z < 2.33 and abs(c.y) > .05 and mx.z < 2.6: p['kind'] = 'leg'
    elif c.z < 2.45 and abs(c.y) <= .05: p['kind'] = 'hips'
    if c.z < .3 and abs(c.y) > .05: p['kind'] = 'shoe'
    p['side'] = 1 if c.y > 0 else -1
    if p['kind'] == 'arm' and abs(c.y) > 1.7: p['kind'] = 'hand'
    if p['kind'] == 'arm' and p['n'] < 30 and abs(c.y) > 1.5: p['kind'] = 'hand'   # manchetter
# hals og kraveting
for p in parts:
    if p['kind'] == 'torso' and p['c'].z > 3.55 and p['mx'].z > 3.8: p['kind'] = 'head'

def part_at(x, y, r=14): return [p for p in parts if near(p, x, y, r)]

# ---- teksturfarver ----
HAIR = np.array([240, 212, 146]) / 255; HAIR_D = np.array([196, 156, 92]) / 255
SHIRT = np.array([150, 192, 226]) / 255; COLLAR = np.array([238, 240, 242]) / 255
SKIN = None
# find hudfarve fra ansigtspladen (jagget bånd)
skin_part = [p for p in parts if p['kind'] == 'head' and 3.95 < p['mn'].z < 4.05 and p['n'] == 56]
SKIN = tex_rgb(200, 440)[:3]
print('hud', SKIN)

mask_shirt = np.zeros((H, W), bool); mask_lapel = np.zeros((H, W), bool)
for p in parts:
    if p['kind'] in ('arm', 'torso') and p['c'].z < 3.7 and p['n'] > 20:
        tris = []
        for f in p['faces']:
            pts = [uv_to_px(*l[uvl].uv) for l in f.loops]
            for k in range(1, len(pts) - 1): tris.append((pts[0], pts[k], pts[k + 1]))
        fill_tris(mask_shirt, tris)
rgb = px[:, :, :3]
def flip(m): return m[::-1]          # maske (y fra toppen) -> pixelrækker (fra bunden)
navy = np.array([38, 76, 100]) / 255
lap = np.array([60, 70, 92]) / 255
m = flip(mask_shirt)
d_navy = np.linalg.norm(rgb - navy, axis=2) < .09
d_lap = np.linalg.norm(rgb - lap, axis=2) < .08
rgb[m & d_navy] = SHIRT
rgb[m & d_lap] = COLLAR
d_slit = np.linalg.norm(rgb - np.array([26, 29, 38]) / 255, axis=2) < .1
rgb[m & d_slit] = SHIRT * .85   # lommestriber bliver til blød skjortesøm
# hår
brown = np.array([139, 92, 74]) / 255
brow = np.array([95, 62, 50]) / 255
rgb[np.linalg.norm(rgb - brown, axis=2) < .06] = HAIR
rgb[np.linalg.norm(rgb - brow, axis=2) < .08] = HAIR_D
# øjne: de to sorte skiver (40,217) og (123,215) -> blå iris med mørk pupil
def paint_eye(cx, cy, r):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.hypot(xx - cx, (H - 1 - yy) - cy)
    rgb[d < r] = np.array([62, 128, 214]) / 255
    rgb[d < r * .38] = np.array([16, 22, 40]) / 255
paint_eye(40, 217, 36); paint_eye(123, 215, 36)
# lille pletter til nye dele: sorte briller (150,250 er sort), hårfarve, hudfarve
PATCH_HAIRD = (358, 162); PATCH_BLACK = (245, 300); PATCH_HAIR = (80, 90); PATCH_SKIN = (200, 440)
img_new = bpy.data.images.new('sebastian_tex', W, H, alpha=False)
out = np.dstack([rgb, np.ones((H, W))]).astype(np.float32)
img_new.pixels = out.ravel()
img_new.filepath_raw = OUT + '/sebastian_tex.png'; img_new.file_format = 'PNG'; img_new.save()
img_new.pack()

# ---- ret på dele ----
def set_uv(p, pxy):
    u, v = pxy[0] / W, 1 - pxy[1] / H
    for f in p['faces']:
        for l in f.loops: l[uvl].uv = (u, v)

# skæg væk: nederste hovedskal bliver hud, så ansigtet er glatbarberet
for p in parts:
    if p['kind'] == 'head' and p['n'] == 208 and p['c'].z < 4.1:
        set_uv(p, PATCH_SKIN)
# kinder, bryn og den takkede ansigtsplade flyttes ind i hovedet (skjult); panden bliver hud på hårhætten foran
for p in parts:
    if p['kind'] != 'head': continue
    if near(p, 40, 288, 26) or near(p, 105, 288, 26) or near(p, 358, 162, 22) or near(p, 389, 165, 22) or (p['n'] == 56 and near(p, 198, 429, 30)):
        for vi in p['verts']: bm.verts[vi].co.x -= .38
        p['gone'] = True
for p in parts:
    if p['kind'] == 'head' and p['n'] in (208, 192) and abs(p['c'].x + .1) < .2 and p['mx'].z - p['mn'].z > .25 and p['mx'].y > .3:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = c + (bm.verts[vi].co - c) * .001
# løse hårkant-stykker i panden skrumpes væk; næsen gøres mindre
for p in parts:
    if p['kind'] == 'head' and p['c'].x > .12 and p['uc'][1] < 180 and p['uc'][0] < 340 and p['n'] < 150:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = c + (bm.verts[vi].co - c) * .001
NC = Vector((.27, 0, 4.22))
for p in parts:
    if p['kind'] == 'head' and 335 < p['uc'][0] < 385 and 212 < p['uc'][1] < 258 and p['c'].x > .2:
        for vi in p['verts']: bm.verts[vi].co = NC + (bm.verts[vi].co - NC) * .72
DROP = .095
for p in parts:
    if p['kind'] != 'head': continue
    eye = any(near(p, x, y, 14) for x, y in ((40, 217), (123, 215), (287, 221), (202, 217))) and p['c'].x > .2
    nose = 335 < p['uc'][0] < 385 and 212 < p['uc'][1] < 258 and p['c'].x > .2
    mouth = near(p, 245, 300, 30) and p['c'].x > .2 and p['n'] < 260
    ear = -.2 < p['c'].x < .1 and abs(p['c'].y) > .25 and p['c'].z > 4.0 and 330 < p['uc'][0] < 480 and p['uc'][1] < 150
    if eye and p['n'] == 28:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = c + (bm.verts[vi].co - c) * .001
        continue
    if eye or nose or mouth or ear:
        d = DROP * (.5 if ear else 1)
        for vi in p['verts']: bm.verts[vi].co.z -= d
# løse skæg-kantstykker (små flader med hårfarve) skrumpes væk
for p in parts:
    if p['kind'] == 'head' and p['n'] <= 6 and p['c'].z < 4.2 and p['uc'][0] < 110 and p['uc'][1] < 160:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = c + (bm.verts[vi].co - c) * .001
# den gamle lille mund skrumpes; en ny, tydeligere smilemund laves nedenfor
for p in parts:
    if p['kind'] == 'head' and near(p, 245, 300, 30) and p['c'].x > .2 and p['n'] < 260:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = c + (bm.verts[vi].co - c) * .001
# bryn mere afslappede (vandret): drej omkring x-aksen gennem midten
for p in parts:
    if False:
        s = 1 if p['c'].y > 0 else -1
        R = Matrix.Rotation(math.radians(-22 * s), 3, 'X')
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = R @ (bm.verts[vi].co - c) + c
# øjne lidt større
for p in parts:
    if p['kind'] == 'head' and (near(p, 40, 217, 12) or near(p, 123, 215, 12)) and p['c'].x > .2:
        c = p['c']
        for vi in p['verts']: bm.verts[vi].co = (bm.verts[vi].co - c) * 1.5 + c
bm.to_mesh(obj.data); bm.free()

# ---- nye dele: hår og briller ----
def make_part(name, build, patch):
    b = bmesh.new(); build(b)
    uv = b.loops.layers.uv.new(UVNAME)
    for f in b.faces:
        for l in f.loops: l[uv].uv = (patch[0] / W, 1 - patch[1] / H)
    me = bpy.data.meshes.new(name); b.to_mesh(me); b.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    return o

def rounded_box(b, center, size, bevel=.08, roll=0.0):
    bmesh.ops.create_cube(b, size=1.0)
    R = Matrix.Rotation(roll, 3, 'X')
    for v in b.verts: v.co = R @ Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
    bmesh.ops.bevel(b, geom=list(b.edges), offset=bevel, segments=4, affect='EDGES')

new_objs = []
def squircle(b, center, radii, pw=.6):
    bmesh.ops.create_uvsphere(b, u_segments=20, v_segments=14, radius=1.0)
    sg = lambda t: (t > 0) - (t < 0)
    for v in b.verts:
        x, y, z = v.co
        co = Vector((sg(x) * abs(x) ** pw * radii[0], sg(y) * abs(y) ** pw * radii[1], sg(z) * abs(z) ** pw * radii[2]))
        if z < 0:                      # underdel: smallere kæbe, spids hage fremad
            t = min(1.0, -z)
            u = max(0.0, (t - .3) / .7); co.y *= 1 - .38 * u * u * (3 - 2 * u)
            if x > 0: co.x += .05 * t ** 2 * x
            co.z -= .02 * t
        v.co = co + Vector(center)
    for f in b.faces: f.smooth = True
def head_loft(b):
    # (z, halv bredde, forkant x, bagkant x, form-eksponent): rund isse, bredde ved kindben, markeret kæbevinkel, fremskudt hage
    L = [(4.51, .17, .08, -.30, 2.3), (4.44, .30, .19, -.46, 2.4), (4.32, .353, .215, -.52, 2.5), (4.16, .35, .218, -.51, 2.7),
         (4.02, .335, .225, -.47, 3.0), (3.93, .315, .232, -.42, 3.5), (3.86, .255, .245, -.36, 3.3), (3.80, .17, .238, -.28, 3.0), (3.765, .07, .215, -.2, 2.4)]
    N = 28; rings = []
    sg = lambda t: (t > 0) - (t < 0)
    for (z, wy, xf, xb, n) in L:
        cx, rx = (xf + xb) / 2, (xf - xb) / 2; ring = []
        for i in range(N):
            th = 2 * math.pi * i / N
            ring.append(b.verts.new((cx + rx * sg(math.cos(th)) * abs(math.cos(th)) ** (2 / n), wy * sg(math.sin(th)) * abs(math.sin(th)) ** (2 / n), z)))
        rings.append(ring)
    for r in range(len(rings) - 1):
        for i in range(N):
            b.faces.new((rings[r][i], rings[r][(i + 1) % N], rings[r + 1][(i + 1) % N], rings[r + 1][i]))
    b.faces.new(list(reversed(rings[0]))); b.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(b, faces=list(b.faces))
    for f in b.faces: f.smooth = True
new_objs.append(make_part('head_new', head_loft, PATCH_SKIN))
new_objs[-1].data.polygons.foreach_set('use_smooth', [True] * len(new_objs[-1].data.polygons))
def ellipsoid(b, center, radii, roll=0.0):
    bmesh.ops.create_uvsphere(b, u_segments=14, v_segments=9, radius=1.0)
    R = Matrix.Rotation(roll, 3, 'X')
    for v in b.verts: v.co = R @ Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2])) + Vector(center)
    for f in b.faces: f.smooth = True
new_objs.append(make_part('hair_top', lambda b: ellipsoid(b, (-.13, 0, 4.40), (.32, .38, .15)), PATCH_HAIR))
new_objs.append(make_part('hair_back', lambda b: ellipsoid(b, (-.29, 0, 4.19), (.31, .45, .35)), PATCH_HAIR))
for sy in (1, -1):
    # forhårsgardin fra midterskilningen, skråner ned mod tindingen
    new_objs.append(make_part('hair_curtain%d' % sy, lambda b, sy=sy: ellipsoid(b, (-.02, sy * .215, 4.47), (.25, .21, .10), roll=-sy * math.radians(20)), PATCH_HAIR))
    # tindingslok foran øret
    new_objs.append(make_part('hair_temple%d' % sy, lambda b, sy=sy: ellipsoid(b, (.06, sy * .365, 4.29), (.12, .05, .15)), PATCH_HAIR))

# midterskilning: smal mørkere stribe langs toppen
new_objs.append(make_part('hair_part', lambda b: rounded_box(b, (-.13, 0, 4.545), (.42, .02, .02), .004), PATCH_HAIRD))

def glasses(b):
    for sy in (1, -1):
        cy = sy * .135
        bmesh.ops.create_circle(b, cap_ends=False, radius=.115, segments=20)
    # (ringe laves som torus herunder i stedet)
new_objs_gl = []
def torus_mesh(name, major, minor, loc):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=24, minor_segments=6, location=loc, rotation=(0, math.radians(90), 0))
    o = bpy.context.active_object; o.name = name
    b = bmesh.new(); b.from_mesh(o.data); uv = b.loops.layers.uv.get(UVNAME) or b.loops.layers.uv.new(UVNAME)
    for f in b.faces:
        for l in f.loops: l[uv].uv = (PATCH_BLACK[0] / W, 1 - PATCH_BLACK[1] / H)
    b.to_mesh(o.data); b.free(); return o
def tube(name, a, c, r):
    a, c = Vector(a), Vector(c)
    d = c - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=6, location=(a + c) / 2)
    o = bpy.context.active_object; o.name = name
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    b = bmesh.new(); b.from_mesh(o.data); uv = b.loops.layers.uv.get(UVNAME) or b.loops.layers.uv.new(UVNAME)
    for f in b.faces:
        for l in f.loops: l[uv].uv = (PATCH_BLACK[0] / W, 1 - PATCH_BLACK[1] / H)
    b.to_mesh(o.data); b.free(); return o
EYE_Z = 4.30 - .095 - .045; FACE_X = .265
for sy in (1, -1):
    new_objs.append(torus_mesh('rim%d' % sy, .092, .011, (FACE_X, sy * .135, EYE_Z)))
    new_objs.append(tube('temple%d' % sy, (FACE_X - .01, sy * .235, EYE_Z + .02), (-.10, sy * .345, EYE_Z + .02), .012))
# smilemund: bue af små rør, ender løftet
MX, MZ, MR = .222, 4.085 - .095, .13
pts = [Vector((MX, MR * math.sin(math.radians(t)), MZ + MR * (1 - math.cos(math.radians(t))))) for t in range(-40, 41, 10)]
for i in range(len(pts) - 1):
    new_objs.append(tube('mund%d' % i, pts[i], pts[i + 1], .017))
new_objs.append(tube('bridge', (FACE_X, .035, EYE_Z + .02), (FACE_X, -.035, EYE_Z + .02), .012))

# ---- transformér til slutorientering: ansigt mod +Z i glTF (= -Y i Blender), skaleret ----
Rz = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Diagonal((S, S, S, 1))
def T(p): return Rz @ Vector(p)

# saml alt i ét objekt
for o in new_objs: o.select_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
# vægte skal sættes på original-delene FØR join: vi gør det via vertex-grupper pr. knogle
BONES = {}
def addb(name, head, tail, parent=None):
    BONES[name] = dict(head=head, tail=tail, parent=parent)
addb('hips', (0, 0, 2.30), (0, 0, 2.75))
addb('spine', (0, 0, 2.75), (0, 0, 3.55), 'hips')
addb('head', (0, 0, 3.55), (0, 0, 4.57), 'spine')
for sd, s in (('L', 1), ('R', -1)):
    addb('upperarm.' + sd, (0, s * .40, 3.38), (0, s * 1.05, 3.38), 'spine')
    addb('forearm.' + sd, (0, s * 1.05, 3.38), (0, s * 1.72, 3.38), 'upperarm.' + sd)
    addb('hand.' + sd, (0, s * 1.72, 3.38), (0, s * 2.42, 3.38), 'forearm.' + sd)
    addb('thigh.' + sd, (0, s * .23, 2.30), (0, s * .23, 1.32), 'hips')
    addb('shin.' + sd, (0, s * .23, 1.32), (0, s * .23, .30), 'thigh.' + sd)
    addb('foot.' + sd, (0, s * .23, .30), (.40, s * .23, .12), 'shin.' + sd)

def sstep(a, b, x):
    t = max(0, min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t)

me = obj.data
# nyt bmesh til at hente vertex-indeks (uændret efter forrige to_mesh)
vg = {n: obj.vertex_groups.new(name=n) for n in BONES}
def put(vi, name, w):
    if w > .001: vg[name].add([vi], w, 'REPLACE')

for p in parts:
    k, sd = p['kind'], 'L' if p['side'] > 0 else 'R'
    for vi in p['verts']:
        co = me.vertices[vi].co
        if k == 'head': put(vi, 'head', 1)
        elif k == 'torso' or k == 'hips':
            if co.z > 3.62: put(vi, 'head', 1)
            elif k == 'hips' or co.z < 2.6:
                w = sstep(2.6, 2.95, co.z); put(vi, 'hips', 1 - w); put(vi, 'spine', w)
            else: put(vi, 'spine', 1)
        elif k in ('arm', 'hand'):
            s = 1 if co.y > 0 else -1; sd2 = 'L' if s > 0 else 'R'; ay = abs(co.y)
            if k == 'hand' or ay > 1.88: put(vi, 'hand.' + sd2, 1)
            else:
                e = sstep(.85, 1.25, ay); w = sstep(1.55, 1.9, ay)
                put(vi, 'spine', 1 - sstep(.25, .6, ay) if False else 0)
                put(vi, 'upperarm.' + sd2, (1 - e)); put(vi, 'forearm.' + sd2, e * (1 - w)); put(vi, 'hand.' + sd2, w)
        elif k == 'leg':
            s = 1 if co.y > 0 else -1; sd2 = 'L' if s > 0 else 'R'
            kn = sstep(1.12, 1.52, co.z)      # 0 = under knæ, 1 = over knæ
            put(vi, 'thigh.' + sd2, kn); put(vi, 'shin.' + sd2, 1 - kn)
        elif k == 'shoe':
            s = 1 if co.y > 0 else -1; put(vi, 'foot.' + ('L' if s > 0 else 'R'), 1)

# nye dele: lad dem vægtes som hoved
for o in new_objs:
    pass

bpy.ops.object.select_all(action='DESELECT')
for o in new_objs: o.select_set(True)
obj.select_set(True); bpy.context.view_layer.objects.active = obj
# vertex-grupper på nye dele
for o in new_objs:
    g = o.vertex_groups.new(name='head'); g.add([v.index for v in o.data.vertices], 1.0, 'REPLACE')
bpy.ops.object.join()
obj = bpy.context.active_object; obj.name = 'sebastian'
# ingen alt-materialer: ét materiale med teksturen
for m in list(obj.data.materials): obj.data.materials.pop(index=0)
mat = bpy.data.materials.new('sebastian'); mat.use_nodes = True
nt = mat.node_tree; bsdf = nt.nodes['Principled BSDF']
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img_new; tx.interpolation = 'Closest'
nt.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 1.0
obj.data.materials.append(mat)
# alle flader bruger materiale 0
for pl in obj.data.polygons: pl.material_index = 0

# transformér mesh
obj.data.transform(Rz); obj.data.update()
for pl in obj.data.polygons: pass
obj.data.calc_normals() if hasattr(obj.data, 'calc_normals') else None
# placér fødder på 0 (originalens z=.07)
minz = min(v.co.z for v in obj.data.vertices)
obj.data.transform(Matrix.Translation((0, 0, -minz)))
FOOT_LIFT = -minz

# ---- skelet ----
arm = bpy.data.armatures.new('rig'); ao = bpy.data.objects.new('rig', arm); bpy.context.collection.objects.link(ao)
bpy.context.view_layer.objects.active = ao; bpy.ops.object.mode_set(mode='EDIT')
for n, d in BONES.items():
    e = arm.edit_bones.new(n)
    e.head = T(d['head']) + Vector((0, 0, FOOT_LIFT)); e.tail = T(d['tail']) + Vector((0, 0, FOOT_LIFT))
for n, d in BONES.items():
    if d['parent']:
        arm.edit_bones[n].parent = arm.edit_bones[d['parent']]
        arm.edit_bones[n].use_connect = (arm.edit_bones[d['parent']].tail - arm.edit_bones[n].head).length < 1e-4
bpy.ops.object.mode_set(mode='OBJECT')
obj.parent = ao
mod = obj.modifiers.new('Armature', 'ARMATURE'); mod.object = ao

# flade normaler for tegneserielook er allerede indbygget i teksturen; glat skygge fra kildedata beholdes
# ---- eksport ----
bpy.ops.object.select_all(action='DESELECT'); ao.select_set(True); obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT + '/sebastian.glb', export_format='GLB', use_selection=True,
                          export_skins=True, export_animations=False, export_yup=True, export_apply=False)

# ---- forhåndsvisning ----
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x = 800; sc.render.resolution_y = 800
sc.world = bpy.data.worlds.new('w'); sc.world.color = (.7, .8, .9)
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'
def shot(name, loc, tgt, scale):
    cam.location = loc; cam.data.ortho_scale = scale
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = OUT + '/sebastian_preview_%s.png' % name; bpy.ops.render.render(write_still=True)
HZ = 3.55
shot('foran', (0, -10, 1.9), (0, 0, 1.9), 4.6)
shot('hoved', (0, -10, HZ), (0, 0, HZ), 1.5)
shot('side', (10, 0, HZ), (0, 0, HZ), 1.5)
shot('bag', (0, 10, HZ), (0, 0, HZ), 1.5)
print('FAERDIG')
