"""Long john til spillet. Kør med:
/Applications/Blender.app/Contents/MacOS/Blender -b --python long_john.py -- <udmappe>

Giver <udmappe>/long_john.glb og to testbilleder. Mål er de samme som i spillet:
fremad er +Z, op er +Y (i Blender: fremad er -Y, op er Z). Delene har drejepunkter, så spillet
kan dreje hjul, forhjul, styr og pedaler.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'
os.makedirs(OUT, exist_ok=True)

# ---------------- farver (samme hex som i spillet) ----------------
PURPLE, PURPLE_D = '#6b2fc0', '#4a1f86'
DARK, BLACK, SILVER, GREY = '#2a2f36', '#1a1d22', '#cfd6dd', '#6b727b'
BROWN, LIME = '#7b4a2f', '#b6ff1a'
BOOKS = ['#e8a0a0', '#e6bf6e', LIME]

bpy.ops.wm.read_factory_settings(use_empty=True)


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex2lin(h, a=1.0):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (lin(r), lin(g), lin(b), a)


MATS = {}


def mat(name, hexcol, rough=.55, metal=0.0, emit=False):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hex2lin(hexcol)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = hex2lin(hexcol)
        b.inputs['Emission Strength'].default_value = 1.0
    MATS[name] = m
    return m


def P(x, y, z):
    """Spillets (x, y, z) -> Blender (x, -z, y)."""
    return Vector((x, -z, y))


def smooth(o):
    for p in o.data.polygons:
        p.use_smooth = True


def link(o, parent):
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()


def empty(name, loc3, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = P(*loc3)
    bpy.context.view_layer.update()
    if parent:
        link(e, parent)
    return e


def finish(o, m, parent, name=None):
    o.data.materials.append(m)
    smooth(o)
    if name:
        o.name = name
    link(o, parent)
    return o


def tube(a3, b3, r, m, parent, verts=14, name=None):
    a, b = P(*a3), P(*b3)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    return finish(o, m, parent, name)


def rbox(size3, loc3, m, parent, bevel=.03, name=None, rot3=(0, 0, 0)):
    sx, sy, sz = size3
    bpy.ops.mesh.primitive_cube_add(size=1, location=P(*loc3))
    o = bpy.context.object
    o.scale = (sx, sz, sy)
    bpy.ops.object.transform_apply(scale=True)
    if rot3 != (0, 0, 0):
        o.rotation_euler = (rot3[0], rot3[2], rot3[1])
    mod = o.modifiers.new('bevel', 'BEVEL')
    mod.width = bevel
    mod.segments = 3
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier='bevel')
    return finish(o, m, parent, name)


def xcyl(loc3, r, depth, m, parent, name=None, verts=24):
    """Cylinder med aksen langs x (sidelæns)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=P(*loc3), rotation=(0, math.pi / 2, 0))
    return finish(bpy.context.object, m, parent, name)


def torus_x(loc3, major, minor, m, parent, name=None, ms=48, mn=12):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=ms, minor_segments=mn,
                                     location=P(*loc3), rotation=(0, math.pi / 2, 0))
    return finish(bpy.context.object, m, parent, name)


def wheel(name, hub3, radius, tire, motor, parent):
    e = empty(name, hub3, parent)
    hx, hy, hz = hub3
    torus_x(hub3, radius - tire, tire, mat('tire', BLACK, .8), e, name + '_daek')
    torus_x(hub3, radius * .8, radius * .03, mat('rim', SILVER, .3, .8), e, name + '_faelg')
    for k in range(6):
        t = k * math.pi / 6
        dy, dz = math.sin(t) * radius * .8, math.cos(t) * radius * .8
        tube((hx, hy + dz, hz - dy), (hx, hy - dz, hz + dy), radius * .016, mat('spoke', '#9aa3ad', .4, .8), e, 6)
    if motor:
        xcyl(hub3, radius * .32, .16, mat('motor', '#b9c0c8', .35, .7), e, name + '_motor')
    else:
        xcyl(hub3, radius * .16, .16, mat('hub', DARK, .5, .5), e, name + '_nav')
    return e


# ---------------- mål (som i spillet) ----------------
RR, FR, RZ, FZ = .58, .5, -1.69, 1.71
BBY, BBZ = .55, -.69

root = empty('long_john', (0, 0, 0))

# ---------------- stel (statisk) ----------------
frame = empty('frame', (0, 0, 0), root)
pm, pd = mat('stel', PURPLE, .35, .1), mat('stel_moerk', PURPLE_D, .4, .1)
tube((0, RR, RZ), (0, BBY, BBZ), .05, pm, frame, name='kaedestag')
tube((0, RR, RZ), (0, 1.33, -1.15), .045, pm, frame, name='saedestag')
tube((0, BBY, BBZ), (0, 1.8, -1.18), .05, pm, frame, name='saederoer')
tube((0, BBY, BBZ), (0, .55, 1.1), .055, pm, frame, name='hovedbjaelke')
tube((0, .66, BBZ + .2), (0, .66, 1.1), .04, pm, frame, name='hovedbjaelke2')
tube((0, .58, 1.1), (0, 1.38, 1.38), .055, pm, frame, name='styrehoved')
tube((0, 1.33, -1.15), (0, 1.33, -.15), .04, pm, frame, name='toppen')
tube((0, .55, -.15), (0, 1.78, -.15), .04, mat('styroer', GREY, .3, .8), frame, name='styroer')
rbox((.08, .34, .9), (0, 1.34, -.58), pd, frame, .02, 'plade')
# bagagebærer, batteri, platform
rbox((.55, .06, 1.2), (0, 1.31, -1.45), pm, frame, .02, 'baerer')
rbox((.36, .2, 1.0), (0, 1.46, -1.5), mat('batteri', '#23272e', .5), frame, .05, 'batteri')
rbox((.12, .05, .12), (-.1, 1.58, -1.15), mat('pol', LIME, .4, emit=True), frame, .01, 'batteri_pol')
rbox((.7, .05, 1.05), (0, .62, .52), mat('platform', '#23272e', .6), frame, .02, 'platform')
for sx in (-.35, .35):
    tube((sx, .6, 0), (sx, .6, 1.05), .02, pm, frame, 8)
# sadel
tube((0, 1.8, -1.18), (0, 1.86, -1.18), .035, mat('saedepind', GREY, .3, .8), frame, 8, 'saedepind')
rbox((.3, .1, .6), (0, 1.9, -1.18), mat('sadel', BROWN, .6), frame, .04, 'sadel')
# bagskærm (halvt hylster over baghjulet)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=RR + .06, depth=.14, location=P(0, RR, RZ),
                                    rotation=(0, math.pi / 2, 0), end_fill_type='NOTHING')
fo = bpy.context.object
bpy.ops.object.transform_apply(rotation=True)       # ringen ligger nu i sidens plan, omkring hjulets midte
bm = bmesh.new(); bm.from_mesh(fo.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.03], context='VERTS')   # behold kun den øvre halvdel
bm.to_mesh(fo.data); bm.free()
mod = fo.modifiers.new('sol', 'SOLIDIFY'); mod.thickness = .025
bpy.context.view_layer.objects.active = fo
bpy.ops.object.modifier_apply(modifier='sol')
finish(fo, mat('skaerm', '#23272e', .5), frame, 'bagskaerm')
rbox((.09, .06, .12), (0, RR + .28, RZ - .55), mat('baglygte', '#d03030', .4, emit=True), frame, .01, 'baglygte')
# kæde (to tynde stænger)
tube((.13, BBY + .2, BBZ), (.13, RR + .12, RZ), .008, mat('kaede', '#3a3f46', .4, .6), frame, 6, 'kaede_top')
tube((.13, BBY - .2, BBZ), (.13, RR - .12, RZ), .008, mat('kaede', '#3a3f46', .4, .6), frame, 6, 'kaede_bund')
# kassette ved baghjulet (statisk detalje)
xcyl((.1, RR, RZ), .2, .05, mat('kassette', '#555b63', .4, .8), frame, 'kassette')
# bøger på platformen
for i, (c, w) in enumerate(zip(BOOKS, (.5, .46, .5))):
    rbox((w, .12, .42), (0, .71 + i * .12, .25 + i * .015), mat('bog%d' % i, c, .6), frame, .015, 'bog%d' % i)

# ---------------- baghjul (drejer) ----------------
wheel('rear_wheel', (0, RR, RZ), RR, .075, False, root)

# ---------------- forgaffel og forhjul ----------------
fork = empty('front_fork', (0, FR, FZ), root)
tube((0, FR, FZ), (0, FR + .89, FZ - .33), .045, pm, fork, name='gaffel')
tube((.1, FR, FZ), (.1, FR + .5, FZ - .18), .02, pm, fork, 8, 'gaffel_side')
rbox((.3, .26, .18), (0, FR + .62, FZ + .22), mat('lygte', DARK, .5), fork, .04, 'lygte')
rbox((.2, .2, .04), (0, FR + .62, FZ + .32), mat('lygtelinse', '#fff2b0', .3, emit=True), fork, .01, 'lygte_glas')
wheel('front_wheel', (0, FR, FZ), FR, .07, True, fork)

# ---------------- styr med tablet (drejer) ----------------
bars = empty('handlebar', (0, 1.82, -.15), root)
xcyl((0, 1.82, -.15), .03, 1.0, mat('styr', DARK, .4, .6), bars, 'styrstang', 12)
for sx in (-.5, .5):
    xcyl((sx, 1.82, -.15), .05, .14, mat('graeb', '#111418', .8), bars, 'graeb', 14)
rbox((.5, .34, .05), (0, 2.06, -.13), mat('tablet', BLACK, .4), bars, .03, 'tablet')
bpy.ops.mesh.primitive_plane_add(size=1, location=P(0, 2.06, -.157), rotation=(-math.pi / 2, 0, math.pi))
sc = bpy.context.object
sc.scale = (.42, .26, 1)
bpy.ops.object.transform_apply(scale=True)
finish(sc, mat('screen', LIME, .3, emit=True), bars, 'tablet_skaerm')

# ---------------- krank og pedaler (drejer) ----------------
crank = empty('crank', (0, BBY, BBZ), root)
xcyl((.1, BBY, BBZ), .22, .04, mat('klinge', DARK, .4, .7), crank, 'klinge', 32)
rbox((.05, .5, .06), (.12, BBY, BBZ), mat('krankarm', DARK, .4, .6), crank, .015, 'krankarm')
rbox((.16, .05, .12), (.2, BBY + .25, BBZ), mat('pedal', BLACK, .7), crank, .01, 'pedal_venstre')
rbox((.16, .05, .12), (-.2, BBY - .25, BBZ), mat('pedal', BLACK, .7), crank, .01, 'pedal_hoejre')

# ---------------- eksport ----------------
glb = os.path.join(OUT, 'long_john.glb')
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', export_apply=True, export_yup=True)
print('GLB gemt:', glb, os.path.getsize(glb) // 1024, 'KB')

# ---------------- testbilleder (kun til preview, ikke med i filen) ----------------
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = 1400, 760
sc.render.image_settings.file_format = 'PNG'
w = bpy.data.worlds.new('verden'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = hex2lin('#a9dcd4')
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
gr = bpy.context.object; gr.data.materials.append(mat('gras', '#7c9f5c', .9))
sun = bpy.data.lights.new('sol', 'SUN'); sun.energy = 3.5
so = bpy.data.objects.new('sol', sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
cam = bpy.data.cameras.new('kam'); cam.lens = 55
co = bpy.data.objects.new('kam', cam); sc.collection.objects.link(co); sc.camera = co
tgt = bpy.data.objects.new('maal', None); sc.collection.objects.link(tgt); tgt.location = P(0, 1.0, 0)
tr = co.constraints.new('TRACK_TO'); tr.target = tgt; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
for name, loc in (('side', P(11, 1.6, 0)), ('skraa', P(7.5, 3.2, 8.0))):
    co.location = loc
    sc.render.filepath = os.path.join(OUT, 'preview_%s.png' % name)
    bpy.ops.render.render(write_still=True)
    print('billede:', sc.render.filepath)
