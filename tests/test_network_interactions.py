import os
import unittest

from playwright.sync_api import sync_playwright


NETWORK_URL = os.environ.get(
    "NETWORK_URL", "http://127.0.0.1:8765/docs/network.html"
)


class NetworkInteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        launch_options = {"headless": True}
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable:
            launch_options["executable_path"] = executable
        cls.browser = cls.playwright.chromium.launch(**launch_options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 900})
        self.console_errors = []
        self.page.on(
            "console",
            lambda message: self.console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        self.page.goto(NETWORK_URL)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_selector("#graph circle")
        self.page.wait_for_timeout(1400)

    def tearDown(self):
        self.page.close()

    def stats(self):
        return {
            "nodes": int(self.page.locator("#stat-visible").inner_text()),
            "edges": int(self.page.locator("#stat-edges").inner_text()),
            "dom_nodes": self.page.locator("#graph circle").count(),
            "dom_edges": self.page.locator("#graph line").count(),
            "zoom": self.page.evaluate(
                "d3.zoomTransform(document.getElementById('graph')).k"
            ),
        }

    def select_person(self, name):
        self.page.locator("#search-box").fill(name)
        self.page.locator("#search-results .item").first.click()
        self.page.wait_for_timeout(1000)

    def assert_all_nodes_in_view(self):
        outside = self.page.evaluate(
            """
            () => {
              const canvas = document.getElementById('canvas-wrap').getBoundingClientRect();
              return [...document.querySelectorAll('#graph circle')].filter(circle => {
                const rect = circle.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                return centerX < canvas.left || centerX > canvas.right ||
                  centerY < canvas.top || centerY > canvas.bottom;
              }).length;
            }
            """
        )
        self.assertEqual(outside, 0)

    def test_search_path_tooltip_and_reset(self):
        initial = self.stats()
        self.assertGreater(initial["nodes"], 1)
        self.assertGreater(initial["edges"], 0)
        self.assertEqual(initial["nodes"], initial["dom_nodes"])
        self.assertEqual(initial["edges"], initial["dom_edges"])
        self.assertEqual(initial["nodes"], 679)
        self.assertEqual(
            self.page.evaluate(
                "allNodes.filter(n => ['釋鑒真','黃巢','吳道子'].includes(n.name)).length"
            ),
            0,
        )
        self.assertGreater(self.page.evaluate("Math.min(...allNodes.map(n => n.degree))"), 0)
        self.assertTrue(self.page.locator("#label-toggle").is_checked())
        self.assertGreater(self.page.locator("#graph .node-label").count(), 0)
        self.assertGreaterEqual(
            self.page.locator("#graph .node-label").first.bounding_box()["height"],
            12,
        )
        self.assert_all_nodes_in_view()

        self.page.locator("#label-toggle-control").click()
        self.assertEqual(self.page.locator("#graph .node-label").count(), 0)
        self.page.locator("#label-toggle-control").click()
        self.assertGreater(self.page.locator("#graph .node-label").count(), 0)

        self.select_person("杜甫")
        searched = self.stats()
        self.assertGreater(searched["nodes"], 1)
        self.assertGreater(searched["edges"], 0)
        self.assertEqual(searched["nodes"], searched["dom_nodes"])
        self.assertEqual(searched["edges"], searched["dom_edges"])
        self.assertAlmostEqual(searched["zoom"], 3, places=2)
        self.assertIn(
            "杜甫",
            self.page.locator("#graph .node-label").all_text_contents(),
        )
        self.page.evaluate(
            """
            const line = document.querySelector('#graph line');
            line.dispatchEvent(new MouseEvent('mouseover', {
              bubbles: true, clientX: 600, clientY: 400
            }));
            """
        )
        self.assertNotEqual(
            self.page.locator("#edge-tooltip .rel-title").inner_text().strip(), ""
        )
        self.assertGreater(
            self.page.locator("#edge-tooltip .rel-item").count(), 0
        )
        self.page.evaluate("document.querySelector('#graph line').dispatchEvent(new MouseEvent('mouseout', {bubbles: true}))")

        self.page.evaluate(
            """
            const target = d3.selectAll('#graph circle')
              .filter(d => d.id !== protagonistId)
              .node();
            target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            """
        )
        self.page.wait_for_timeout(800)
        path = self.stats()
        self.assertGreaterEqual(path["nodes"], 2)
        self.assertGreater(path["edges"], 0)

        self.page.locator("#zoom-reset").click()
        self.page.wait_for_timeout(1400)
        reset = self.stats()
        self.assertEqual(self.page.locator("#search-box").input_value(), "")
        self.assertEqual(reset["nodes"], initial["nodes"])
        self.assertEqual(reset["edges"], initial["edges"])
        self.assertEqual(reset["dom_nodes"], initial["dom_nodes"])
        self.assertEqual(reset["dom_edges"], initial["dom_edges"])
        self.assert_all_nodes_in_view()
        self.assertTrue(self.page.locator("#label-toggle").is_checked())

        self.select_person("杜甫")
        self.page.locator("#graph .graph-background").click(
            position={"x": 12, "y": 12}
        )
        self.page.wait_for_timeout(1400)
        background_reset = self.stats()
        self.assertEqual(background_reset["nodes"], initial["nodes"])
        self.assertEqual(background_reset["edges"], initial["edges"])
        self.assert_all_nodes_in_view()

        screenshot = os.environ.get("NETWORK_SCREENSHOT")
        if screenshot:
            self.page.screenshot(path=screenshot)
        self.assertEqual(self.console_errors, [])


if __name__ == "__main__":
    unittest.main()
