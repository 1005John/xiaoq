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


if __name__ == "__main__":
    unittest.main()
