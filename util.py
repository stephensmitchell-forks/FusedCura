import sys
import traceback

from adsk.core import MessageBoxIconTypes, MessageBoxButtonTypes
from adsk.fusion import CustomGraphicsCoordinates, CustomGraphicsAppearanceColorEffect, CustomGraphicsPointTypes
from .Fusion360Utilities.Fusion360Utilities import AppObjects

handlers = []


def report_exc(fun):
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            message = 'Error:\n{}\n--\n{}'.format(
                ''.join(traceback.format_exception_only(exc_type, exc_value)),
                '\n'.join(traceback.format_tb(exc_traceback)))
            print(message)
            print(message, file=sys.stderr)
            AppObjects().ui.messageBox(message, 'An error occured', MessageBoxButtonTypes.OKButtonType,
                                       MessageBoxIconTypes.CriticalIconType)

    return wrap


def event(clazz, handler):
    class Handler(clazz):
        @report_exc
        def notify(self, args):
            handler(args)

    handler_instance = Handler()
    handlers.append(handler_instance)
    return handler_instance


def register_on(clazz, obj):
    def wrapper(func):
        handler = event(clazz, func)
        obj.add(handler)

    return wrapper


def recursive_inputs(node, inputs, type_creator):
    for (k, val) in node.items():
        if val['type'] == 'category':
            new_input = inputs.addGroupCommandInput(k, val['label'])
            local_inputs = new_input.children
        else:
            new_input = type_creator(k, val, inputs)
            if not new_input:
                continue
            local_inputs = inputs
        new_input.tooltipDescription = val['description']
        new_input.tooltip = k
        if val.get('children'):
            recursive_inputs(val.get('children'), local_inputs, type_creator)


def display_machine(graphics, max_x, max_y, max_z, center_is_zero):
    ao = AppObjects()
    c_x, c_y = (0, 0) if center_is_zero else (max_x / 2, max_y / 2)
    origin = [0.0 - c_x, 0.0 - c_y, 0.0]
    furthest_x = [max_x - c_x, 0.0 - c_y, 0.0]
    furthest_corner = [max_x - c_x, max_y - c_y, 0.0]
    furthest_y = [0.0 - c_x, max_y - c_y, 0.0]
    bottom_loop = [origin, furthest_x, furthest_corner, furthest_y]
    bottom_coords = list([float(coord) for point in bottom_loop for coord in point])
    bottom_custom = CustomGraphicsCoordinates.create(bottom_coords)
    appearances = ao.app.materialLibraries.itemByName('Fusion 360 Appearance Library').appearances
    bed_appearance = ao.design.appearances.itemByName('bedAppearance')
    if not bed_appearance:
        bed_appearance = ao.design.appearances.addByCopy(
            appearances.itemByName('Plastic - Translucent Matte (Blue)'),
            'bedAppearance')
    bed_mesh = graphics.addMesh(bottom_custom, [0, 1, 2, 0, 2, 3], [], [])
    bed_mesh.color = CustomGraphicsAppearanceColorEffect.create(bed_appearance)
    bed_mesh.setOpacity(0.3, True)
    limits = graphics.addLines(bottom_custom, [0, 1, 1, 2, 2, 3, 3, 0], False)
    limits.weight = 3
    limits.depthPriority = 1
    top_loop = [[x, y, max_z] for [x, y, _] in [origin, furthest_x, furthest_corner, furthest_y]]
    top_coords = [float(coord) for point in top_loop for coord in point] + bottom_coords
    created = CustomGraphicsCoordinates.create(top_coords)
    limits_top = graphics.addLines(created, [0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 1, 5, 2, 6, 3, 7], False)
    limits_top.weight = 1
    limits_top.setOpacity(0.6, True)
    limits_top.depthPriority = 1
    origin = graphics.addPointSet(CustomGraphicsCoordinates.create([0, 0, 0]), [0],
                                  CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType, 'origin/16x16.png')
    origin.depthPriority = 1
