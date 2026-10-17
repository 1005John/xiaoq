"""Product-side contract tests. No hardware, network, or product main import."""

import ast
import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from bluebot_integration import BluebotIntegration
from vendor.hardware_expression_system import MobileWorkStatus
from vendor.hardware_expression_system.characters.xiaoq_visuals import (
    CUTE_IDLE_P,
    IDLE_P,
    CuteRenderer,
    CuteStyle,
    Renderer,
)


class FakePlayer:
    def __init__(self):
        self.statuses = []
        self.draws = []
        self.resets = []
        self.fail = False

    def reset(self, now_ms=None):
        self.resets.append(now_ms)

    def set_status(self, status, now_ms):
        self.statuses.append((status, now_ms))

    def draw(self, surface, now_ms):
        if self.fail:
            raise RuntimeError("test draw failure")
        self.draws.append((surface, now_ms))


class BluebotIntegrationTest(unittest.TestCase):
    def test_product_main_keeps_switch_and_draw_calls(self):
        main = Path(__file__).resolve().parents[1] / "robot_face_v11_fc245e4.py"
        tree = ast.parse(main.read_text(encoding="utf-8"))
        strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertIn("character_set", strings)
        self.assertIn("mobilework_status", strings)
        calls = {
            (node.func.value.id, node.func.attr)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        }
        self.assertIn(("bluebot_controller", "set_character"), calls)
        self.assertIn(("bluebot_controller", "set_status"), calls)
        self.assertIn(("bluebot_controller", "draw"), calls)
        self.assertIn(("bluebot_controller", "draw_xiaoq_transition"), calls)
        self.assertIn(("renderer", "draw_mobilework_fallback"), calls)
        self.assertIn("WAITING_INPUT", strings)
        self.assertIn("PLANNING", strings)
        self.assertIn("EXPERT_ROUTING", strings)
        self.assertIn("TOOL_RUNNING", strings)
        self.assertIn("COMPLETED", strings)
        self.assertIn("FAILED", strings)

    def test_explicit_switch_and_status_validation(self):
        player = FakePlayer()
        bridge = BluebotIntegration(player)
        surface = object()
        self.assertFalse(bridge.draw(surface, 100))
        self.assertFalse(bridge.set_character("unknown"))
        self.assertFalse(bridge.set_status("NOT_A_STATUS", 100))
        self.assertFalse(bridge.set_status(None, 100))
        self.assertEqual(player.statuses, [])
        self.assertTrue(bridge.set_status("blocked", 120))
        self.assertEqual(player.statuses, [(MobileWorkStatus.BLOCKED, 120)])
        self.assertTrue(bridge.set_character("bluebot"))
        self.assertEqual(player.resets, [None])
        self.assertTrue(bridge.draw(surface, 140))
        self.assertEqual(player.draws, [(surface, 140)])
        self.assertTrue(bridge.set_character("xiaoq"))
        self.assertFalse(bridge.draw(surface, 160))
        self.assertTrue(bridge.set_character("bluebot", 200))
        self.assertEqual(player.resets, [None, 200])

    def test_renderer_failure_restores_legacy_mode(self):
        player = FakePlayer()
        bridge = BluebotIntegration(player)
        bridge.set_character("bluebot")
        player.fail = True
        self.assertFalse(bridge.draw(object(), 100))
        self.assertFalse(bridge.enabled)
        self.assertIn("RuntimeError", bridge.last_error)

    def test_character_switch_and_rapid_reversal_keep_visible_frame(self):
        class ColorPlayer(FakePlayer):
            def draw(self, surface, now_ms):
                surface.fill((0, 45, 110))

        surface = pygame.Surface((64, 36))
        surface.fill((240, 208, 192))
        bridge = BluebotIntegration(ColorPlayer())
        bridge.set_character("bluebot", 1000, surface)
        self.assertTrue(bridge.draw(surface, 1000))
        self.assertEqual(surface.get_at((32, 18))[:3], (240, 208, 192))

        bridge.draw(surface, 1120)
        visible = surface.get_at((32, 18))[:3]
        bridge.set_character("xiaoq", 1120, surface)
        surface.fill((240, 208, 192))
        bridge.draw_xiaoq_transition(surface, 1120)
        self.assertEqual(surface.get_at((32, 18))[:3], visible)

        surface.fill((240, 208, 192))
        bridge.draw_xiaoq_transition(surface, 1220)
        visible = surface.get_at((32, 18))[:3]
        bridge.set_character("bluebot", 1220, surface)
        bridge.draw(surface, 1220)
        self.assertEqual(surface.get_at((32, 18))[:3], visible)

        bridge.set_character("xiaoq", 1220, surface)
        surface.fill((240, 208, 192))
        bridge.draw_xiaoq_transition(surface, 1780)
        self.assertEqual(surface.get_at((32, 18))[:3], (240, 208, 192))
        self.assertFalse(bridge.transition.active)

    def test_character_switch_reveals_live_target_without_blank_field(self):
        class ColorPlayer(FakePlayer):
            def draw(self, surface, now_ms):
                surface.fill((0, 45, 110))

        surface = pygame.Surface((128, 72))
        surface.fill((240, 208, 192))
        bridge = BluebotIntegration(ColorPlayer())
        bridge.set_character("bluebot", 1000, surface)
        self.assertTrue(bridge.draw(surface, 1220))
        self.assertEqual(surface.get_at((64, 36))[:3], (0, 45, 110))
        self.assertEqual(surface.get_at((2, 36))[:3], (240, 208, 192))

        bridge.draw(surface, 1560)
        bridge.set_character("xiaoq", 1600, surface)
        surface.fill((240, 208, 192))
        bridge.draw_xiaoq_transition(surface, 1820)
        self.assertEqual(surface.get_at((64, 36))[:3], (240, 208, 192))
        self.assertEqual(surface.get_at((2, 36))[:3], (0, 45, 110))

    def test_duplicate_character_command_does_not_restart_transition(self):
        class ColorPlayer(FakePlayer):
            def draw(self, surface, now_ms):
                surface.fill((0, 45, 110))

        surface = pygame.Surface((64, 36))
        surface.fill((240, 208, 192))
        bridge = BluebotIntegration(ColorPlayer())
        bridge.set_character("bluebot", 1000, surface)
        bridge.draw(surface, 1120)
        bridge.set_character("bluebot", 1120, surface)
        bridge.draw(surface, 1560)
        self.assertEqual(surface.get_at((32, 18))[:3], (0, 45, 110))
        self.assertFalse(bridge.transition.active)

    def test_role_reversal_before_a_draw_keeps_current_frame(self):
        surface = pygame.Surface((64, 36))
        surface.fill((240, 208, 192))
        bridge = BluebotIntegration(FakePlayer())
        bridge.set_character("bluebot", 1000, surface)
        bridge.set_character("xiaoq", 1000, surface)
        self.assertFalse(bridge.enabled)
        self.assertFalse(bridge.transition.active)
        surface.fill((240, 208, 192))
        bridge.draw_xiaoq_transition(surface, 1240)
        self.assertEqual(surface.get_at((32, 18))[:3], (240, 208, 192))

    def test_failed_bluebot_draw_cancels_switch(self):
        player = FakePlayer()
        player.fail = True
        bridge = BluebotIntegration(player)
        surface = pygame.Surface((64, 36))
        bridge.set_character("bluebot", 100, surface)
        self.assertFalse(bridge.draw(surface, 120))
        self.assertFalse(bridge.transition.active)


class RenderSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.display.set_mode((1280, 720))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_mobilework_statuses_draw(self):
        bridge = BluebotIntegration()
        bridge.set_character("bluebot")
        for index, status in enumerate(MobileWorkStatus):
            now_ms = 1000 + index * 800
            self.assertTrue(bridge.set_status(status.value, now_ms))
            self.assertTrue(bridge.draw(self.surface, now_ms + 500), status.value)

    def test_xiaoq_cute_and_neon_draw(self):
        Renderer(self.surface).draw(IDLE_P)
        CuteRenderer(self.surface).draw(CUTE_IDLE_P)
        self.assertEqual(self.surface.get_at((0, 0))[:3], (240, 208, 192))

    def test_mobilework_fallback_does_not_change_xiaoq_palette(self):
        renderer = Renderer(self.surface)
        neon = renderer.get_neon_color()
        pupil = CuteStyle.PUPIL_COLOR
        renderer.draw_mobilework_fallback(IDLE_P)
        self.assertEqual(self.surface.get_at((0, 0))[:3], (0, 71, 187))
        self.assertEqual(self.surface.get_at((350, 310))[:3], (232, 248, 245))
        self.assertEqual(renderer.get_neon_color(), neon)
        self.assertEqual(CuteStyle.PUPIL_COLOR, pupil)

    def test_character_switch_round_trip_with_both_xiaoq_styles(self):
        for style, renderer_type, idle in (
            ("cute", CuteRenderer, CUTE_IDLE_P),
            ("neon", Renderer, IDLE_P),
        ):
            with self.subTest(style=style):
                xiaoq = renderer_type(self.surface)
                xiaoq.draw(idle)
                xiaoq_pixel = self.surface.get_at((0, 0))[:3]
                bridge = BluebotIntegration()
                bridge.set_character("bluebot", 1000, self.surface)
                for offset in (0, 60, 230, 290, 560):
                    self.assertTrue(bridge.draw(self.surface, 1000 + offset))
                self.assertNotEqual(self.surface.get_at((0, 0))[:3], xiaoq_pixel)

                bridge.set_character("xiaoq", 1600, self.surface)
                for offset in (0, 60, 230, 290, 560):
                    xiaoq.draw(idle)
                    expected = self.surface.get_at((0, 0))[:3]
                    bridge.draw_xiaoq_transition(self.surface, 1600 + offset)
                self.assertEqual(self.surface.get_at((0, 0))[:3], expected)


if __name__ == "__main__":
    unittest.main()
