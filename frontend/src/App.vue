<script setup>
import { useAuth } from './composables/useAuth';
import Login from './views/Login.vue';
import Dashboard from './views/Dashboard.vue';
const { estaAutenticado, usuario, cerrarSesion } = useAuth();
</script>
<template>
  <div class="app-root">
    <Login v-if="!estaAutenticado" />
    <div v-else>
      <div class="user-session-bar">
        <span> Usuario: <strong>{{ usuario?.nombre || usuario?.expediente }}</strong> (Rol: {{ usuario?.rol }})</span>
        <button @click="cerrarSesion" class="btn-primary-gio" style="color:  #0f172a;">Cerrar Sesión</button>
      </div>
      <Dashboard />
    </div>
  </div>
</template>
<style>
.app-root {
  min-height: 100vh;
  background-color: #0f172a;
  color: #f8fafc;
}
.user-session-bar {
  background-color: #020617;
  padding: 0.4rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: #94a3b8;
  border-bottom: 1px solid #1e293b;
}
.btn-logout {
  background: transparent;
  border: 1px solid #334155;
  color: #f87171;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
}
.btn-logout:hover {
  background-color: rgba(239, 68, 68, 0.1);
}
</style>