"""Recuperación de contraseña por correo: un enlace de un solo uso que vence."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

UsuarioGIO = get_user_model()


def enlace_de_recuperacion(usuario, request):
    """El token deja de servir en cuanto cambia la contraseña o el usuario vuelve a entrar."""
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    base = settings.URL_PUBLICA or request.build_absolute_uri('/').rstrip('/')
    return f'{base}/restablecer/{uid}/{token}'


def enviar_correo_de_recuperacion(usuario, request):
    minutos = settings.PASSWORD_RESET_TIMEOUT // 60
    mensaje = (
        f'Hola, {usuario.nombre_completo}:\n\n'
        f'Recibimos una solicitud para crear una nueva contraseña de su cuenta GIO '
        f'({usuario.expediente}).\n\n'
        f'Abra este enlace en los próximos {minutos} minutos:\n\n'
        f'{enlace_de_recuperacion(usuario, request)}\n\n'
        'El enlace sirve una sola vez. Si usted no lo pidió, ignore este correo: su contraseña '
        'no cambia.\n\n'
        'Sistema GIO — CASE Puebla'
    )
    send_mail('GIO — Recuperación de contraseña', mensaje, None, [usuario.email])


def usuario_del_enlace(uid, token):
    """Usuario activo al que pertenece el enlace, o None si es inválido, ya se usó o venció."""
    try:
        usuario = UsuarioGIO.objects.get(pk=force_str(urlsafe_base64_decode(uid)), is_active=True)
    except (TypeError, ValueError, OverflowError, UsuarioGIO.DoesNotExist):
        return None
    return usuario if default_token_generator.check_token(usuario, token) else None
