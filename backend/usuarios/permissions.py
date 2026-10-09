from rest_framework.permissions import SAFE_METHODS, BasePermission


class EsAdmin(BasePermission):
    message = 'Solo la Gerencia puede realizar esta operación.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.es_admin)


class PuedeAsignar(BasePermission):
    message = 'Solo Subgerencia o Gerencia pueden asignar o reasignar folios.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.puede_asignar)


class PuedeCrearIncidente(BasePermission):
    message = 'Los folios se crean por ingesta SISA o por Subgerencia/Gerencia.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        accion = getattr(view, 'action', None)
        if accion == 'create':
            return request.user.puede_asignar
        if accion == 'destroy':
            return request.user.es_admin
        return True


class PuedeEditarIncidente(BasePermission):
    message = 'No tiene permisos para modificar este folio.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if request.method in SAFE_METHODS:
            return True
        if user.tiene_vision_global:
            return True
        if user.es_evaluador:
            return obj.evaluador_id == user.id
        if user.es_tecnico:
            return obj.tecnico_id == user.id
        return False
