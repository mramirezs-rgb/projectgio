from django.contrib.auth.models import AbstractUser
from django.db import models
class UsuarioGIO(AbstractUser):
    ROLES = (
        ('TECNICO', 'Planta Externa (Técnico)'),
        ('PI_EVALUADOR', 'Planta Interna (Evaluador / Rango Bajo)'),
        ('PI_SUB', 'Planta Interna (Subgerencia)'),
        ('ADMIN', 'Gerencia / Administración'),
    )
    AREAS = (
        ('Puebla', 'Puebla'),
        ('Pachuca', 'Pachuca'),
        ('Veracruz', 'Veracruz'),
        ('Poza Rica', 'Poza Rica'),
        ('Jalapa', 'Jalapa'),
        ('Tlaxcala', 'Tlaxcala'),
        ('Córdoba', 'Córdoba'),
        ('Coatzacoalcos', 'Coatzacoalcos'),
    )
    expediente = models.CharField(max_length=20, unique=True, help_text="Expediente TELMEX (Ej. OQU-8821)")
    rol = models.CharField(max_length=15, choices=ROLES, default='PI_EVALUADOR')
    area_operativa = models.CharField(max_length=50, choices=AREAS, blank=True, null=True)
    USERNAME_FIELD = 'expediente'
    REQUIRED_FIELDS = ['username', 'email']
    def __str__(self):
        return f"{self.expediente} - {self.first_name} {self.last_name} ({self.get_rol_display()})"