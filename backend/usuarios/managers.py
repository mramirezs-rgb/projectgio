from django.contrib.auth.base_user import BaseUserManager


class UsuarioGIOManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, expediente, password, **extra):
        if not expediente:
            raise ValueError('El expediente es obligatorio.')
        expediente = str(expediente).strip().upper()
        extra.setdefault('username', expediente.lower().replace(' ', '.'))
        email = extra.pop('email', '')
        usuario = self.model(expediente=expediente, email=self.normalize_email(email or ''), **extra)
        usuario.set_password(password)
        usuario.full_clean(exclude=['password'], validate_unique=False)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, expediente, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._crear(expediente, password, **extra)

    def create_superuser(self, expediente, password=None, **extra):
        extra['is_staff'] = True
        extra['is_superuser'] = True
        extra.setdefault('rol', self.model.Rol.ADMIN)
        return self._crear(expediente, password, **extra)

    def get_by_natural_key(self, expediente):
        return self.get(expediente__iexact=str(expediente).strip())
