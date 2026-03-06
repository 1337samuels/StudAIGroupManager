#!/usr/bin/env python3
"""
Internationalization (i18n) Support
Multi-language support for the UI.
Gated behind ENABLE_MULTI_LANGUAGE_SUPPORT flag.
"""

import os
import json
import logging

from config.feature_flags import (
    ENABLE_MULTI_LANGUAGE_SUPPORT,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)

# Default language
DEFAULT_LANGUAGE = 'en'

# Translation dictionaries
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
        'no_bookings': 'No bookings found',
        'ai_planning': 'AI is planning your week...',
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
        'no_bookings': 'No se encontraron reservas',
        'ai_planning': 'La IA esta planificando tu semana...',
        'booking_success': 'Sala reservada exitosamente!',
        'booking_failed': 'La reserva de sala fallo',
    },
    'fr': {
        'app_title': 'Gestionnaire de Groupes d\'Etude LBS',
        'assignments': 'Devoirs',
        'room_booking': 'Reservation de Salle',
        'weekly_plan': 'Plan Hebdomadaire',
        'study_sessions': 'Sessions d\'Etude',
        'members': 'Membres',
        'settings': 'Parametres',
        'dark_mode': 'Mode Sombre',
        'language': 'Langue',
        'submit': 'Soumettre',
        'cancel': 'Annuler',
        'save': 'Enregistrer',
        'delete': 'Supprimer',
        'loading': 'Chargement...',
        'error': 'Erreur',
        'success': 'Succes',
        'login': 'Connexion',
        'logout': 'Deconnexion',
        'due_date': 'Date d\'echeance',
        'course': 'Cours',
        'priority': 'Priorite',
        'export_pdf': 'Exporter en PDF',
        'book_room': 'Reserver une Salle',
        'plan_week': 'Planifier Ma Semaine',
        'no_assignments': 'Aucun devoir trouve',
        'no_bookings': 'Aucune reservation trouvee',
        'ai_planning': 'L\'IA planifie votre semaine...',
        'booking_success': 'Salle reservee avec succes!',
        'booking_failed': 'La reservation a echoue',
    },
    'de': {
        'app_title': 'LBS Lerngruppen-Manager',
        'assignments': 'Aufgaben',
        'room_booking': 'Raumbuchung',
        'weekly_plan': 'Wochenplan',
        'study_sessions': 'Lernsitzungen',
        'members': 'Mitglieder',
        'settings': 'Einstellungen',
        'dark_mode': 'Dunkler Modus',
        'language': 'Sprache',
        'submit': 'Absenden',
        'cancel': 'Abbrechen',
        'save': 'Speichern',
        'delete': 'Loschen',
        'loading': 'Laden...',
        'error': 'Fehler',
        'success': 'Erfolg',
        'login': 'Anmelden',
        'logout': 'Abmelden',
        'due_date': 'Falligkeitsdatum',
        'course': 'Kurs',
        'priority': 'Prioritat',
        'export_pdf': 'Als PDF exportieren',
        'book_room': 'Raum buchen',
        'plan_week': 'Meine Woche planen',
        'no_assignments': 'Keine Aufgaben gefunden',
        'no_bookings': 'Keine Buchungen gefunden',
        'ai_planning': 'KI plant Ihre Woche...',
        'booking_success': 'Raum erfolgreich gebucht!',
        'booking_failed': 'Raumbuchung fehlgeschlagen',
    },
    'zh': {
        'app_title': 'LBS 学习小组管理器',
        'assignments': '作业',
        'room_booking': '房间预订',
        'weekly_plan': '周计划',
        'study_sessions': '学习会议',
        'members': '成员',
        'settings': '设置',
        'dark_mode': '深色模式',
        'language': '语言',
        'submit': '提交',
        'cancel': '取消',
        'save': '保存',
        'delete': '删除',
        'loading': '加载中...',
        'error': '错误',
        'success': '成功',
        'login': '登录',
        'logout': '退出',
        'due_date': '截止日期',
        'course': '课程',
        'priority': '优先级',
        'export_pdf': '导出PDF',
        'book_room': '预订房间',
        'plan_week': '规划我的一周',
        'no_assignments': '未找到作业',
        'no_bookings': '未找到预订',
        'ai_planning': 'AI正在规划您的一周...',
        'booking_success': '房间预订成功！',
        'booking_failed': '房间预订失败',
    },
}


class I18nManager:
    """
    Internationalization manager.
    Gated behind ENABLE_MULTI_LANGUAGE_SUPPORT flag.
    """

    def __init__(self, default_language=None):
        self.default_language = default_language or DEFAULT_LANGUAGE
        self.current_language = self.default_language

        if ENABLE_MULTI_LANGUAGE_SUPPORT:
            logger.info(f"I18n initialized with {len(TRANSLATIONS)} languages")
        else:
            logger.debug("Multi-language support is disabled, using English only")

    def set_language(self, language_code):
        """Set the current language"""
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return

        if language_code in TRANSLATIONS:
            self.current_language = language_code
            logger.info(f"Language set to: {language_code}")
        else:
            logger.warning(f"Language not supported: {language_code}")

    def translate(self, key, language=None):
        """Get a translated string"""
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key)

        lang = language or self.current_language
        translations = TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANGUAGE, {}))
        return translations.get(key, key)

    def get_available_languages(self):
        """Get list of available languages"""
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return [DEFAULT_LANGUAGE]

        return list(TRANSLATIONS.keys())

    def get_all_translations(self, language=None):
        """Get all translations for a language"""
        if not ENABLE_MULTI_LANGUAGE_SUPPORT:
            return TRANSLATIONS.get(DEFAULT_LANGUAGE, {})

        lang = language or self.current_language
        return TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANGUAGE, {}))


# Convenience function
def t(key, language=None):
    """Translate a key to the current language"""
    manager = I18nManager()
    return manager.translate(key, language)
