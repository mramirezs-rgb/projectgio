from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

from .managers import UsuarioGIOManager


class UsuarioGIO(AbstractUser):
    class Rol(models.TextChoices):
        TECNICO = 'TECNICO', 'Técnico de planta externa'
        PI_EVALUADOR = 'PI_EVALUADOR', 'Técnico'
        PI_SUB = 'PI_SUB', 'Planta Interna (Subgerencia)'
        ADMIN = 'ADMIN', 'Gerencia / Administración'

    class Area(models.TextChoices):
        PUEBLA = 'PUEBLA', 'Puebla'
        PACHUCA = 'PACHUCA', 'Pachuca'
        VERACRUZ = 'VERACRUZ', 'Veracruz'
        POZA_RICA = 'POZA RICA', 'Poza Rica'
        JALAPA = 'JALAPA', 'Jalapa'
        TLAXCALA = 'TLAXCALA', 'Tlaxcala'
        CORDOBA = 'CORDOBA', 'Córdoba'
        COATZACOALCOS = 'COATZACOALCOS', 'Coatzacoalcos'
        QUINTANA_ROO = 'QUINTANA ROO', 'Quintana Roo'
        # No es una zona: ahí quedan los usuarios dados de baja para no mezclarse con las demás.
        BAJA = 'BAJA', 'Baja'

    ROLES_VISION_GLOBAL = (Rol.PI_SUB, Rol.ADMIN)
    # Técnicos de planta externa e interna: trabajan por zona y deben tener un área.
    ROLES_CON_AREA = (Rol.TECNICO, Rol.PI_EVALUADOR)

    expediente = models.CharField(
        max_length=20,
        unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9._-]{3,20}$',
                                   'El expediente admite letras, dígitos, punto, guion y guion bajo.')],
        help_text='Identificador corporativo de acceso (Ej. OQU-8821).',
    )
    username = models.CharField(max_length=150, unique=True, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.TECNICO, db_index=True)
    area_operativa = models.CharField(max_length=50, choices=Area.choices, blank=True, default='')
    telefono = models.CharField(max_length=20, blank=True, default='')

    USERNAME_FIELD = 'expediente'
    REQUIRED_FIELDS = []

    objects = UsuarioGIOManager()

    class Meta:
        verbose_name = 'usuario GIO'
        verbose_name_plural = 'usuarios GIO'
        ordering = ['expediente']

    def __str__(self):
        return f'{self.expediente} — {self.nombre_completo} ({self.get_rol_display()})'

    def save(self, *args, **kwargs):
        self.expediente = self.expediente.strip().upper()
        if not self.username:
            self.username = self.expediente.lower().replace(' ', '.')
        if self.area_operativa:
            self.area_operativa = self.area_operativa.strip().upper()
        return super().save(*args, **kwargs)

    @classmethod
    def areas_operativas(cls):
        """Áreas que puede tener un usuario activo, como pares (valor, nombre)."""
        return [(valor, nombre) for valor, nombre in cls.Area.choices if valor != cls.Area.BAJA]

    def dar_de_baja(self):
        """Desactiva la cuenta y la pasa al área de bajas; sus folios históricos se conservan."""
        self.is_active = False
        self.area_operativa = self.Area.BAJA
        self.save(update_fields=['is_active', 'area_operativa'])

    @property
    def requiere_area(self):
        return self.rol in self.ROLES_CON_AREA

    @property
    def nombre_completo(self):
        return self.get_full_name().strip() or self.username or self.expediente

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.is_superuser

    @property
    def es_subgerencia(self):
        return self.rol == self.Rol.PI_SUB

    @property
    def es_evaluador(self):
        return self.rol == self.Rol.PI_EVALUADOR

    @property
    def es_tecnico(self):
        return self.rol == self.Rol.TECNICO

    @property
    def tiene_vision_global(self):
        return self.es_admin or self.es_subgerencia

    @property
    def puede_asignar(self):
        return self.es_admin or self.es_subgerencia

    @property
    def puede_gestionar_usuarios(self):
        return self.es_admin
