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
        self.page.wait_for_timeout(500)

    def tearDown(self):
        self.page.close()

    def stats(self):
        return self.page.evaluate(
            """
            () => ({
              nodes: +document.getElementById('stat-visible').textContent,
              edges: +document.getElementById('stat-edges').textContent,
              domNodes: document.querySelectorAll('#graph circle').length,
              domEdges: document.querySelectorAll('#graph line').length,
              labels: document.querySelectorAll('#graph .node-label').length,
              zoom: d3.zoomTransform(document.getElementById('graph')).k,
            })
            """
        )

    def node_positions(self):
        return self.page.evaluate(
            """
            () => [...document.querySelectorAll('#graph circle')]
              .slice(0, 40)
              .map(node => [node.__data__.id, +node.getAttribute('cx'), +node.getAttribute('cy')])
            """
        )

    def set_label_density(self, level):
        self.page.locator("#label-density").fill(str(level))
        self.page.wait_for_timeout(180)

    def select_person(self, name):
        self.page.locator("#search-box").fill(name)
        self.page.locator("#search-results .item").first.click()
        self.page.wait_for_timeout(850)

    def label_overlap_count(self):
        return self.page.evaluate(
            """
            () => {
              const labels = [...document.querySelectorAll('#graph .node-label')]
                .map(label => label.getBoundingClientRect());
              let overlaps = 0;
              for (let i = 0; i < labels.length; i += 1) {
                for (let j = i + 1; j < labels.length; j += 1) {
                  const a = labels[i], b = labels[j];
                  if (a.left < b.right && a.right > b.left &&
                      a.top < b.bottom && a.bottom > b.top) overlaps += 1;
                }
              }
              return overlaps;
            }
            """
        )

    def largest_node_diameter(self):
        return self.page.evaluate(
            """
            () => Math.max(...[...document.querySelectorAll('#graph circle')]
              .map(circle => circle.getBoundingClientRect().width))
            """
        )

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

    def test_controls_adaptive_labels_box_zoom_and_reset(self):
        initial = self.stats()
        initial_positions = self.node_positions()
        self.assertEqual(initial["nodes"], 679)
        self.assertEqual(initial["nodes"], initial["domNodes"])
        self.assertEqual(initial["edges"], initial["domEdges"])
        self.assertGreater(initial["edges"], 0)
        self.assertGreater(initial["labels"], 0)
        self.assert_all_nodes_in_view()

        for removed_filter in ("era", "degree", "role"):
            self.assertEqual(self.page.locator(f"#combo-{removed_filter}").count(), 0)
        self.assertEqual(
            self.page.locator("#sidebar .guide").count(), 1
        )
        self.assertEqual(self.page.locator("#highlight-mode").count(), 0)
        self.assertEqual(
            self.page.locator("#legend h4").all_text_contents(),
            ["关系类型", "节点颜色", "节点大小"],
        )
        self.assertEqual(
            self.page.locator("#legend").inner_text().count("男性"), 1
        )
        self.assertEqual(
            self.page.locator("#legend").inner_text().count("女性"), 1
        )

        label_counts = []
        for level in range(6):
            self.set_label_density(level)
            label_counts.append(self.stats()["labels"])
            self.assertEqual(self.label_overlap_count(), 0)
        self.assertEqual(label_counts[0], 0)
        self.assertTrue(
            all(after > before for before, after in zip(label_counts, label_counts[1:])),
            label_counts,
        )
        self.assertEqual(
            self.page.locator("#graph .label-leader").count(), label_counts[-1]
        )

        self.set_label_density(2)
        before_zoom_label_height = self.page.locator(
            "#graph .node-label"
        ).first.bounding_box()["height"]
        before_zoom_node_diameter = self.largest_node_diameter()
        self.assertGreaterEqual(before_zoom_label_height, 14)

        self.page.locator("#select-mode").click()
        canvas = self.page.locator("#canvas-wrap").bounding_box()
        self.page.mouse.move(canvas["x"] + 30, canvas["y"] + 50)
        self.page.mouse.down()
        self.page.mouse.move(
            canvas["x"] + canvas["width"] * 0.58,
            canvas["y"] + canvas["height"] * 0.58,
            steps=12,
        )
        self.page.mouse.up()
        self.page.wait_for_timeout(700)

        boxed = self.stats()
        self.assertGreater(boxed["zoom"], initial["zoom"])
        self.assertEqual(boxed["nodes"], initial["nodes"])
        self.assertEqual(boxed["edges"], initial["edges"])
        self.assertEqual(self.node_positions(), initial_positions)
        after_zoom_label_height = self.page.locator(
            "#graph .node-label"
        ).first.bounding_box()["height"]
        self.assertAlmostEqual(
            after_zoom_label_height, before_zoom_label_height, delta=1.5
        )
        after_zoom_node_diameter = self.largest_node_diameter()
        self.assertLessEqual(
            after_zoom_node_diameter, before_zoom_node_diameter * 1.3
        )
        visible_labels = self.page.evaluate(
            """
            () => {
              const canvas = document.getElementById('canvas-wrap').getBoundingClientRect();
              return [...document.querySelectorAll('#graph .node-label')].every(label => {
                const rect = label.getBoundingClientRect();
                return rect.right >= canvas.left && rect.left <= canvas.right &&
                  rect.bottom >= canvas.top && rect.top <= canvas.bottom;
              });
            }
            """
        )
        self.assertTrue(visible_labels)

        self.select_person("杜甫")
        self.assertEqual(self.page.locator("#search-selection .person-chip").count(), 1)
        one_center_nodes = self.stats()["nodes"]
        self.select_person("李白")
        searched = self.stats()
        self.assertGreater(searched["nodes"], 1)
        self.assertGreater(searched["edges"], 0)
        self.assertGreaterEqual(searched["nodes"], one_center_nodes)
        self.assertEqual(self.page.locator("#search-selection .person-chip").count(), 2)
        self.assertEqual(
            set(self.page.locator("#search-selection .person-chip").all_text_contents()),
            {"杜甫✕", "李白✕"},
        )
        label_texts = self.page.locator("#graph .node-label").all_text_contents()
        self.assertIn("杜甫", label_texts)
        self.assertIn("李白", label_texts)
        self.assertEqual(self.label_overlap_count(), 0)

        self.set_label_density(4)
        self.assertGreater(self.stats()["labels"], 8)
        self.assertEqual(self.label_overlap_count(), 0)
        screenshot = os.environ.get("NETWORK_SCREENSHOT")
        if screenshot:
            self.page.screenshot(path=screenshot, full_page=True)

        self.page.locator("#zoom-reset").click()
        self.page.wait_for_timeout(750)
        reset = self.stats()
        self.assertEqual(self.page.locator("#search-box").input_value(), "")
        self.assertEqual(self.page.locator("#label-density").input_value(), "2")
        self.assertEqual(reset["nodes"], initial["nodes"])
        self.assertEqual(reset["edges"], initial["edges"])
        self.assertEqual(reset["domNodes"], initial["domNodes"])
        self.assertEqual(reset["domEdges"], initial["domEdges"])
        self.assertAlmostEqual(reset["zoom"], initial["zoom"], places=3)
        self.assertEqual(self.node_positions(), initial_positions)
        self.assert_all_nodes_in_view()

        self.assertEqual(self.console_errors, [])


if __name__ == "__main__":
    unittest.main()
