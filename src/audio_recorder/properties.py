import sounddevice as sd
from mo.core import Properties, PropertySelectOption, Settings, translate

def get_microphone_options() -> list[PropertySelectOption]:
    options = []
    devices = sd.query_devices()
    input_devices =[d for d in devices if d['max_input_channels']>0]
    if not input_devices:
        options.append(PropertySelectOption(label = translate("no_input_devices"), value = -1))
        return options
    for index, device in enumerate(input_devices):
        label = device['name']
        options.append(PropertySelectOption(label = label, value = index))
    return options

def on_microphone_change(props: Properties, settings: Settings):
    return props._properties

def get_properties() -> Properties:
    props = Properties()
    microphone_options = get_microphone_options()
    props.add_select("option_microphone", translate("select_microphone"), microphone_options)
    if microphone_options:
        props.set_default("option_microphone", microphone_options[0].value)

    props.add_int("SR", translate("sample_rate"), min = 4000, max = 200000, step = 100)
    props.set_default("SR",44100)

    return props
