# Ubicación: logic/enfermedad.py

# --- LISTA DE CLASES (NO CAMBIAR EL ORDEN) ---
clase = [
    "Sarna (Roña)",
    "Pudricion Negra",
    "Roya del Cedro",
    "Sana",
    "Sano",
    "Oidio (Cenicilla)",
    "Sana",
    "Mancha Foliar por Cercospora (Mancha Gris)",
    "Roya Comun",
    "Tizon Foliar del Norte",
    "Sano",
    "Pudrición Negra",
    "Yesca (Sarampión Negro)",
    "Tizon Foliar (Mancha de Isariopsis)",
    "Sana",
    "Huanglongbing (Enverdecimiento de Citricos)",
    "Mancha Bacteriana",
    "Sano",
    "Mancha Bacteriana",
    "Sano",
    "Tizon Temprano",
    "Tizon Tardío",
    "Sana",
    "Sana",
    "Sana",
    "Oídio (Cenicilla)",
    "Chamuscado de Hoja",
    "Sana",
    "Mancha Bacteriana",
    "Tizon Temprano",
    "Tizon Tardío",
    "Moho de la Hoja",
    "Mancha Foliar por Septoria",
    "Ácaros (Araña Roja)",
    "Mancha Diana",
    "Virus del Enrollamiento de Hoja Amarilla",
    "Virus del Mosaico",
    "Sano"
]

# --- DICCIONARIO DE DESCRIPCIONES (SOLO SÍNTOMAS) ---
descripciones = {
    "Sana": "La planta presenta un desarrollo normal, con hojas de color uniforme y sin signos de patógenos.",
    "Sano": "La planta presenta un desarrollo normal, con hojas de color uniforme y sin signos de patógenos.",
    "Sarna (Roña)": "Infección fúngica que produce manchas oscuras, aterciopeladas o costras deformantes en hojas y frutos.",
    "Pudricion Negra": "Enfermedad que causa manchas circulares de color marrón rojizo que se oscurecen, provocando que el fruto se arrugue y momifique.",
    "Roya del Cedro": "Hongo caracterizado por manchas brillantes de color amarillo anaranjado en la superficie superior de las hojas.",
    "Oidio (Cenicilla)": "Aparición de una capa de polvo blanco o grisáceo que cubre la superficie de hojas, tallos y brotes nuevos.",
    "Mancha Foliar por Cercospora (Mancha Gris)": "Presencia de pequeñas manchas circulares de color gris pálido o tostado con bordes oscuros bien definidos.",
    "Roya Comun": "Desarrollo de pústulas elevadas de color rojizo o canela en ambas superficies de las hojas, que liberan esporas polvorientas.",
    "Tizon Foliar del Norte": "Lesiones alargadas en forma de cigarro, de color gris verdoso a bronceado, que aparecen inicialmente en las hojas inferiores.",
    "Yesca (Sarampión Negro)": "Enfermedad de la madera que provoca decoloración interna y un patrón atigrado o clorosis entre las nervaduras de las hojas.",
    "Tizon Foliar (Mancha de Isariopsis)": "Manchas angulares o irregulares de color marrón rojizo con bordes definidos, visibles principalmente en hojas maduras.",
    "Huanglongbing (Enverdecimiento de Citricos)": "Enfermedad bacteriana sistémica que causa un moteado asimétrico y amarillento en las hojas y deformación en los frutos.",
    "Mancha Bacteriana": "Pequeñas lesiones oscuras, húmedas y angulares en las hojas, a menudo rodeadas por un halo amarillo.",
    "Tizon Temprano": "Manchas marrones oscuras con anillos concéntricos (aspecto de diana) que aparecen primero en las hojas más viejas.",
    "Tizon Tardío": "Manchas grandes, irregulares y de aspecto acuoso o aceitoso de color verde pálido a marrón oscuro, a menudo con moho blanco en condiciones húmedas.",
    "Chamuscado de Hoja": "Necrosis o muerte del tejido que comienza en los bordes de la hoja y avanza hacia el centro, a menudo delimitada por una banda amarilla.",
    "Moho de la Hoja": "Manchas amarillas difusas en el haz de la hoja que corresponden a zonas de moho verde oliva o marrón en el envés.",
    "Mancha Foliar por Septoria": "Numerosas manchas circulares pequeñas con centro grisáceo y borde oscuro, que suelen contener pequeños puntos negros en el centro.",
    "Ácaros (Araña Roja)": "Punteado amarillento o bronceado fino en las hojas causado por picaduras, a veces acompañado de finas telarañas.",
    "Mancha Diana": "Lesiones circulares de color marrón rojizo a marrón oscuro con anillos concéntricos claros y oscuros alternados.",
    "Virus del Enrollamiento de Hoja Amarilla": "Clorosis (amarillamiento) fuerte en los márgenes de las hojas, que se engrosan y se enrollan hacia arriba en forma de cuchara.",
    "Virus del Mosaico": "Patrón irregular de coloración con zonas verde claro y verde oscuro alternadas, acompañado a menudo de deformación o arrugamiento de la hoja.",
    "Oídio (Cenicilla)": "Aparición de una capa de polvo blanco o grisáceo que cubre la superficie de hojas y tallos."
}

def obtener_descripcion(nombre_enfermedad):
    """Devuelve la descripción del síntoma o un mensaje genérico."""
    return descripciones.get(nombre_enfermedad, "Se han detectado anomalías visuales en la hoja que requieren inspección detallada.")