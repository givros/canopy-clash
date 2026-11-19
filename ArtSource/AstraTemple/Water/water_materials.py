"""Native Unreal material graphs for the spring, cascades and waterside flora."""
import unreal as ue


ROOT = "/Game/AstraTemple/Water"
MEL = ue.MaterialEditingLibrary
PROP = ue.MaterialProperty

NOISE = """
struct FStreamNoise {
    float h(float2 p) {
        float3 q = frac(float3(p.xyx)*float3(.1031,.11369,.13787));
        q += dot(q,q.yzx+19.19); return frac((q.x+q.y)*q.z);
    }
    float n(float2 p) {
        float2 i=floor(p), f=frac(p); f=f*f*(3.-2.*f);
        return lerp(lerp(h(i),h(i+float2(1,0)),f.x),
                    lerp(h(i+float2(0,1)),h(i+1.),f.x),f.y);
    }
    float f(float2 p) {
        return n(p)*.57+n(p*2.16+17.8)*.28+n(p*4.31-8.6)*.15;
    }
}; FStreamNoise w;
"""


class Graph:
    def __init__(self, name, model=None, blend=None, two_sided=False):
        path = ROOT + "/" + name
        self.mat = ue.load_asset(path) if ue.EditorAssetLibrary.does_asset_exist(path) else None
        if self.mat is None:
            self.mat = ue.AssetToolsHelpers.get_asset_tools().create_asset(
                name, ROOT, ue.Material, ue.MaterialFactoryNew())
        if not self.mat:
            raise RuntimeError(path)
        self.mat.modify()
        MEL.delete_all_material_expressions(self.mat)
        self.mat.set_editor_properties({
            "shading_model": model or ue.MaterialShadingModel.MSM_DEFAULT_LIT,
            "blend_mode": blend or ue.BlendMode.BLEND_OPAQUE,
            "two_sided": two_sided
        })
        if blend == ue.BlendMode.BLEND_TRANSLUCENT and model != ue.MaterialShadingModel.MSM_UNLIT:
            self.mat.set_editor_property("translucency_lighting_mode", ue.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        self.inputs = {}
        self.row = 0

    def node(self, kind, x, y):
        return MEL.create_material_expression(self.mat, kind, x, y)

    def scalar(self, value, output=None):
        node = self.node(ue.MaterialExpressionConstant, -520, self.row)
        self.row += 130
        node.set_editor_property("r", value)
        if output:
            self.out(node, output)
        return node

    def vector(self, value, output=None):
        node = self.node(ue.MaterialExpressionConstant3Vector, -520, self.row)
        self.row += 140
        node.set_editor_property("constant", ue.LinearColor(*value, 1.0))
        if output:
            self.out(node, output)
        return node

    def source(self, key):
        if key in self.inputs:
            return self.inputs[key]
        classes = {
            "P": ue.MaterialExpressionWorldPosition, "T": ue.MaterialExpressionTime,
            "Refl": ue.MaterialExpressionReflectionVectorWS, "Eye": ue.MaterialExpressionCameraVectorWS,
            "UV": ue.MaterialExpressionTextureCoordinate,
            "Tint": ue.MaterialExpressionVertexColor, "Weight": ue.MaterialExpressionVertexColor
        }
        node = self.node(classes[key], -1320, len(self.inputs)*220)
        self.inputs[key] = (node, "A" if key == "Weight" else "")
        return self.inputs[key]

    def code(self, label, source, channels, keys=(), output=None):
        n = self.node(ue.MaterialExpressionCustom, -720, self.row)
        self.row += 224
        inputs = []
        for key in keys:
            pin = ue.CustomInput()
            pin.set_editor_property("input_name", key)
            inputs.append(pin)
        n.set_editor_properties({
            "description": label,
            "output_type": getattr(ue.CustomMaterialOutputType, "CMOT_FLOAT" + str(channels)),
            "inputs": inputs,
            "code": source
        })
        for key in keys:
            origin, pin = self.source(key)
            if not MEL.connect_material_expressions(origin, pin, n, key):
                raise RuntimeError((label, key))
        if output:
            self.out(n, output)
        return n

    def out(self, n, target):
        if not MEL.connect_material_property(n, "", target):
            raise RuntimeError(str(target))

    def tint_in_exposure(self, color):
        eye = self.node(ue.MaterialExpressionEyeAdaptationInverse, -160, self.row)
        self.row += 140
        if not MEL.connect_material_expressions(color, "", eye, ""):
            raise RuntimeError("Exposure compensation")
        self.out(eye, PROP.MP_EMISSIVE_COLOR)

    def finish(self):
        errors = MEL.recompile_material(self.mat)
        if errors:
            raise RuntimeError((self.mat.get_name(), list(errors)))
        if not ue.EditorAssetLibrary.save_loaded_asset(self.mat, False):
            raise RuntimeError(self.mat.get_path_name())
        return self.mat.get_name()


def spring():
    g = Graph("M_SpringWater", ue.MaterialShadingModel.MSM_SINGLE_LAYER_WATER, two_sided=True)
    g.vector((.017,.036,.038), PROP.MP_BASE_COLOR)
    g.scalar(.27, PROP.MP_SPECULAR)
    g.scalar(.245, PROP.MP_ROUGHNESS)
    g.scalar(.075, PROP.MP_OPACITY)
    g.code("Crossing wind and river ripples", NOISE + """
        float2 p=P.xy*.01;
        p+=float2(w.f(p*.47+T*.027)-.5,w.f(p*.36+17.-T*.033)-.5)*1.42;
        float sweep=sin(dot(p,float2(.27,.36))+.23*T);
        float pixelSpan=max(length(ddx(p)),length(ddy(p)));
        float detail=1.-smoothstep(.04,.31,pixelSpan);
        float fine=1.-smoothstep(.025,.12,pixelSpan);
        float2 gradient=float2(.010,.006)*cos(dot(p,float2(.86,1.13))-.63*T)
                 +float2(.012,-.018)*cos(dot(p,float2(1.55,-2.18))+T*.97+sweep*.8)
                 +float2(.016,.010)*cos(dot(p,float2(3.31,1.76))-T*1.76+sweep*1.3)*detail
                 +float2(-.005,.009)*cos(dot(p,float2(-5.2,8.6))-T*2.3+sweep*.86)*fine;
        return normalize(float3(gradient,1.));""", 3, ("P","T"), PROP.MP_NORMAL)
    minerals=g.code("Suspended green minerals over depths and shelves", NOISE + """
        float sand=saturate(Tint.r)*(.84+.16*w.f(P.xy*.008));
        return lerp(float3(.008,.028,.024),float3(.029,.065,.046),sand);
        """, 3, ("P","Tint"))
    probe_path="/Game/AstraTemple/Lighting/T_PoolSurroundings"
    if ue.EditorAssetLibrary.does_asset_exist(probe_path):
        lookup=g.code("Project the basin reflection ray onto the surrounding banks", """
            float3 d=sign(Refl+1e-6)*max(abs(Refl),.001);
            float3 wall=lerp(float3(-6500,-4400,-480),float3(1700,4420,4800),step(0.,d));
            float3 travel=(wall-P)/d;
            return normalize(P+d*max(0.,min(travel.x,min(travel.y,travel.z)))-float3(-1760,120,122));
            """,3,("P","Refl"))
        sample=g.node(ue.MaterialExpressionTextureSample,-300,200)
        sample.set_editor_properties({"texture":ue.load_asset(probe_path),"sampler_type":ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR})
        MEL.connect_material_expressions(lookup,"",sample,"Coordinates")
        reflect=g.code("Fresnel reflection of the local forest and stone", """
            float basin=(1.-smoothstep(100.,260.,abs(P.z)))*(1.-smoothstep(1200.,2200.,P.x));
            return basin*(.07+.55*pow(saturate(1.-abs(Eye.z)),3.5));""",1,("P","Eye"))
        reflected=g.node(ue.MaterialExpressionMultiply,-35,160)
        MEL.connect_material_expressions(sample,"RGB",reflected,"A")
        MEL.connect_material_expressions(reflect,"",reflected,"B")
        total=g.node(ue.MaterialExpressionAdd,110,345)
        MEL.connect_material_expressions(minerals,"",total,"A")
        MEL.connect_material_expressions(reflected,"",total,"B")
        minerals=total
    g.tint_in_exposure(minerals)
    water = g.node(ue.MaterialExpressionSingleLayerWaterMaterialOutput, 0, 750)
    ports = MEL.get_material_expression_input_names(water)
    coefficients = [
        g.vector((.00058,.00148,.00121)), g.vector((.0073,.00245,.00298)), g.scalar(.11),
        g.code("Sunlight on the submerged bed", """
          float2 p=P.xy*.014;
          float a=sin(p.x*1.43+sin(p.y*.83+T*.37)+T*.58);
          float b=sin(p.y*1.53+sin(p.x*.92-T*.42)-T*.49);
          float caustic=pow(saturate(1.-abs(a+b)*1.65),4.);
          return float3(.98,1.,.94)*(1.+caustic*.23);""", 3, ("P","T"))
    ]
    if len(ports) != len(coefficients):
        raise RuntimeError(list(ports))
    for source, pin in zip(coefficients, ports):
        if not MEL.connect_material_expressions(source, "", water, pin):
            raise RuntimeError(str(pin))
    return g.finish()


def bed():
    g = Graph("M_SubmergedGravel", two_sided=True)
    g.code("Alluvial gravel and moss", NOISE + """
        float2 p=P.xy*.01; float s=w.f(p*.61+2.3); float grit=w.f(p*23.7);
        float shoal=w.n(p*.21); float pocket=smoothstep(.47,.68,s+.07*grit);
        float3 rock=lerp(float3(.085,.109,.073),float3(.32,.275,.156),saturate(grit*1.36-.21));
        float3 moss=lerp(float3(.044,.088,.050),float3(.138,.173,.068),shoal);
        return lerp(rock,moss,pocket)*(.72+.38*grit);""", 3, ("P",), PROP.MP_BASE_COLOR)
    g.scalar(.72, PROP.MP_ROUGHNESS)
    return g.finish()


FALL_FLOW = NOISE + """
    float2 q=UV;
    float shift=(w.n(float2(q.y*.12-T*.42,3.2))-.5)*.23;
    float u=q.x+shift+(w.n(q*float2(.71,.095)+float2(0.,-T*.65))-.5)*.17;
    float main=w.f(float2(u*2.1, q.y*.23-T*1.62));
    float fine=w.f(float2(u*8.4+.35*main, q.y*.76-T*4.84));
    float vein=pow(saturate(.58*main+.60*fine),1.45);
"""


def cascade():
    g = Graph("M_CascadeVeil", blend=ue.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    g.mat.set_editor_property("translucency_lighting_mode", ue.TranslucencyLightingMode.TLM_VOLUMETRIC_NON_DIRECTIONAL)
    g.vector((.68,.79,.80), PROP.MP_BASE_COLOR)
    g.code("Openings between falling strands", FALL_FLOW + """
        float veil=pow(smoothstep(.18,.77,vein),1.3);
        return saturate(Weight*(.25+veil*.74));""", 1, ("UV","T","Weight"), PROP.MP_OPACITY)
    g.tint_in_exposure(g.vector((.18,.21,.22)))
    g.scalar(.24, PROP.MP_ROUGHNESS)
    return g.finish()


def foam():
    g = Graph("M_BrokenFoam", blend=ue.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    g.vector((.72,.82,.75), PROP.MP_BASE_COLOR)
    g.tint_in_exposure(g.vector((.12,.15,.14)))
    g.code("Bubbles dissolving and reforming", NOISE + """
        float2 s=P.xy*.01; float2 p=s*4.+float2(T*.27,-T*.18);
        float n=w.f(p); float low=w.f(s*1.3-float2(T*.19,T*.08));
        float filaments=pow(saturate(1.-abs(n-.50)*5.4),2.2);
        return saturate(Weight*(.08+filaments*.87)*smoothstep(.18,.66,low+.19));""",
        1, ("P","T","Weight"), PROP.MP_OPACITY)
    g.scalar(.33, PROP.MP_ROUGHNESS)
    return g.finish()


def mist():
    g = Graph("M_SprayMist", ue.MaterialShadingModel.MSM_UNLIT, ue.BlendMode.BLEND_TRANSLUCENT, True)
    daylight = g.node(ue.MaterialExpressionEyeAdaptationInverse, -100, 200)
    light = g.vector((.72,.83,.88))
    if not MEL.connect_material_expressions(light, "", daylight, ""):
        raise RuntimeError("Mist exposure compensation")
    g.out(daylight, PROP.MP_EMISSIVE_COLOR)
    g.code("Turbulent spray fading into air", NOISE + """
        float2 p=UV-.5;
        float rim=saturate(1.-dot(p,p)*4.35);
        float cloud=w.f(P.xy*.009+float2(P.z*.014-T*.63,P.z*.005+T*.27));
        return saturate(rim*rim*smoothstep(.18,.74,cloud)*Weight*.70);""",
        1, ("UV","P","T","Weight"), PROP.MP_OPACITY)
    return g.finish()


def botany():
    g = Graph("M_LiliesAndLotus", two_sided=True)
    g.code("Leaf veins and petal stripes", """
        float r=UV.y; float taper=smoothstep(.09,.47,r)*(1.-smoothstep(.91,.999,r));
        float a=UV.x*6.28318;
        float vein=pow(saturate(cos(a*11.+r*.83)),37.)*taper;
        float skin=.94+.065*cos(a*24.+r*17.)+.025*sin(a*33.-r*28.);
        return Tint*(skin-.22*vein)*(.75+.25*r);""",
        3, ("UV","Tint"), PROP.MP_BASE_COLOR)
    g.scalar(.39, PROP.MP_ROUGHNESS)
    return g.finish()


def build():
    ue.EditorAssetLibrary.make_directory(ROOT)
    return [fn() for fn in (spring,bed,cascade,foam,mist,botany)]
