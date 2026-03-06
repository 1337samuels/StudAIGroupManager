#!/usr/bin/env python3
"""
Accessibility Utilities
Enhanced accessibility features for screen readers, high contrast, etc.
Gated behind ENABLE_ACCESSIBILITY_MODE flag.
"""

import logging

from config.feature_flags import (
    ENABLE_ACCESSIBILITY_MODE,
    is_flag_enabled,
    feature_flag,
)

logger = logging.getLogger(__name__)


class AccessibilityManager:
    """
    Manages accessibility features.
    Gated behind ENABLE_ACCESSIBILITY_MODE flag.
    """

    def __init__(self):
        if not ENABLE_ACCESSIBILITY_MODE:
            logger.debug("Accessibility mode is disabled")
            return

        self.high_contrast = False
        self.large_text = False
        self.screen_reader_mode = False
        self.reduced_motion = False
        self.keyboard_navigation = True
        logger.info("AccessibilityManager initialized")

    @feature_flag('ENABLE_ACCESSIBILITY_MODE')
    def get_accessibility_settings(self):
        """Get current accessibility settings"""
        return {
            'high_contrast': self.high_contrast,
            'large_text': self.large_text,
            'screen_reader_mode': self.screen_reader_mode,
            'reduced_motion': self.reduced_motion,
            'keyboard_navigation': self.keyboard_navigation,
        }

    @feature_flag('ENABLE_ACCESSIBILITY_MODE')
    def update_settings(self, settings):
        """Update accessibility settings"""
        if 'high_contrast' in settings:
            self.high_contrast = settings['high_contrast']
        if 'large_text' in settings:
            self.large_text = settings['large_text']
        if 'screen_reader_mode' in settings:
            self.screen_reader_mode = settings['screen_reader_mode']
        if 'reduced_motion' in settings:
            self.reduced_motion = settings['reduced_motion']
        if 'keyboard_navigation' in settings:
            self.keyboard_navigation = settings['keyboard_navigation']

        logger.info(f"Accessibility settings updated: {settings}")
        return self.get_accessibility_settings()

    @feature_flag('ENABLE_ACCESSIBILITY_MODE')
    def get_css_classes(self):
        """Get CSS classes for current accessibility settings"""
        classes = []
        if self.high_contrast:
            classes.append('a11y-high-contrast')
        if self.large_text:
            classes.append('a11y-large-text')
        if self.screen_reader_mode:
            classes.append('a11y-screen-reader')
        if self.reduced_motion:
            classes.append('a11y-reduced-motion')
        return ' '.join(classes)

    @feature_flag('ENABLE_ACCESSIBILITY_MODE')
    def generate_aria_attributes(self, element_type, label=None, description=None):
        """Generate ARIA attributes for an element"""
        attrs = {}
        if label:
            attrs['aria-label'] = label
        if description:
            attrs['aria-describedby'] = description
        if element_type == 'button':
            attrs['role'] = 'button'
            attrs['tabindex'] = '0'
        elif element_type == 'navigation':
            attrs['role'] = 'navigation'
        elif element_type == 'main':
            attrs['role'] = 'main'
        elif element_type == 'alert':
            attrs['role'] = 'alert'
            attrs['aria-live'] = 'polite'
        return attrs
