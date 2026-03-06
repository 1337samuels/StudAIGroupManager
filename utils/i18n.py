#!/usr/bin/env python3
"""Internationalization (i18n) Support. Gated behind ENABLE_MULTI_LANGUAGE_SUPPORT."""

import logging

from config.feature_flags import (
    ENABLE_MULTI_LANGUAGE_SUPPORT, is_flag_enabled, feature_flag,
)

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = 'en'

TRANSLATIONS = {
    'en': {
        'app_title': 'LBS Study Group Manager',
        'assignments': 'Assignments',
        'room_booking': 'Room Booking',
        'weekly_plan': 'Weekly Plan',
        'study_sessions': 'Study Sessions',
        'members': 'Members',
        'settings': 'Settings',
        'dark_mode': 'Dark Mode',
        'language': 'Language',
        'submit': 'Submit',
        'cancel': 'Cancel',
        'save': 'Save',
        'delete': 'Delete',
        'loading': 'Loading...',
        'error': 'Error',
        'success': 'Success',
        'login': 'Login',
        'logout': 'Logout',
        'due_date': 'Due Date',
        'course': 'Course',
        'priority': 'Priority',
        'export_pdf': 'Export to PDF',
        'book_room': 'Book Room',
        'plan_week': 'Plan My Week',
        'no_assignments': 'No assignments found',
        'booking_success': 'Room booked successfully!',
        'booking_failed': 'Room booking failed',
    },
    'es': {
        'app_title': 'Gestor de Grupos de Estudio LBS',
        'assignments': 'Tareas',
        'room_booking': 'Reserva de Sala',
        'weekly_plan': 'Plan Semanal',
        'study_sessions': 'Sesiones de Estudio',
        'members': 'Miembros',
        'settings': 'Configuracion',
        'dark_mode': 'Modo Oscuro',
        'language': 'Idioma',
        'submit': 'Enviar',
        'cancel': 'Cancelar',
        'save': 'Guardar',
        'delete': 'Eliminar',
        'loading': 'Cargando...',
        'error': 'Error',
        'success': 'Exito',
        'login': 'Iniciar Sesion',
        'logout': 'Cerrar Sesion',
        'due_date': 'Fecha de Entrega',
        'course': 'Curso',
        'priority': 'Prioridad',
        'export_pdf': 'Exportar a PDF',
        'book_room': 'Reservar Sala',
        'plan_week': 'Planificar Mi Semana',
        'no_assignments': 'No se encontraron tareas',
        'booking_success': 'Sala reservada exitosamente!',
        'booking_failed': 'La reserva de sala fallo',
    },
}


class I18nManager:
    """Internationalization manager. Gated behind ENABLE_MULTI_LANGUAGE_SUPPORT."""

    def __init__(self, default_language=None):
        self.default_language = default_language or DEFAULT_LANGUAGE
        self.current_language = self.default_language
        if ENABLE_MULTI_LANGUAGE_SUPPORT:
            logger.info(f"I18n initialized with {len(TRANSLATIONS)} languages")

    def set_language(self, language_code):
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return
        if language_code in TRANSLATIONS:
            self.current_language = language_code

    def translate(self, key, language=None):
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key)
        lang = language or self.current_language
        return TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANGUAGE, {})).get(key, key)

    def get_available_languages(self):
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return [DEFAULT_LANGUAGE]
        return list(TRANSLATIONS.keys())

    def get_all_translations(self, language=None):
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return TRANSLATIONS.get(DEFAULT_LANGUAGE, {})
        lang = language or self.current_language
        return TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANGUAGE, {}))


def t(key, language=None):
    """Translate a key to the current language."""
    return I18nManager().translate(key, language)
