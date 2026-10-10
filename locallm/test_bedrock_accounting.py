"""Budget failures must stop inference rather than silently free reservations."""
import json
import copy
import concurrent.futures
import http.client
import io
import math
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error

import bedrock_proxy as proxy


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.jsonl'

    def ledger(self, cap=1):
        ledger = proxy.Ledger(self.path, cap)
        if hasattr(ledger, 'close'):
            self.addCleanup(ledger.close)
        return ledger

    def reservation(self, ledger, amount):
        result = ledger.reserve(amount)
        self.assertTrue(result)
        # The original API returned bool and settled by amount; the journaled
        # API returns an identity so duplicate settlements can be rejected.
        return amount if result is True else result

    def test_pending_reservation_survives_restart(self):
        first = self.ledger()
        self.assertTrue(first.reserve(.75))
        if hasattr(first, 'close'):
            first.close()
        restarted = self.ledger()
        self.assertFalse(restarted.reserve(.5))

    def test_unknown_usage_consumes_reserved_amount(self):
        ledger = self.ledger()
        ticket = self.reservation(ledger, .75)
        ledger.settle(ticket, {'status': 504})
        self.assertFalse(ledger.reserve(.5))

    def test_valid_usage_releases_only_unused_reservation(self):
        ledger = self.ledger()
        ticket = self.reservation(ledger, .75)
        ledger.settle(ticket, {'status': 200, 'usd': .25})
        self.assertAlmostEqual(ledger.spent, .25)
        self.assertTrue(ledger.reserve(.75))
        self.assertFalse(ledger.reserve(.01))

    def test_corrupt_history_is_not_skipped(self):
        self.path.write_text('{"usd": 0.5}\n{"usd":', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.ledger()

    def test_nonfinite_and_nonpositive_caps_are_rejected(self):
        for cap in (0, -1, math.inf, math.nan):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                self.ledger(cap)

    def test_invalid_charges_are_not_loaded_as_credit(self):
        for value in (-1, math.inf, math.nan):
            with self.subTest(value=value):
                self.path.write_text(json.dumps({'usd': value}) + '\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.ledger()

    def test_overrun_stops_further_requests(self):
        ledger = self.ledger(cap=10)
        ticket = self.reservation(ledger, .5)
        ledger.settle(ticket, {'status': 200, 'usd': 1})
        self.assertFalse(ledger.reserve(.1))

    def test_a_second_writer_is_refused(self):
        self.ledger()
        with self.assertRaises((RuntimeError, OSError)):
            self.ledger()

    def test_symlink_alias_cannot_bypass_the_writer_lock(self):
        self.ledger().reserve(.1)
        alias = self.path.with_name('alias.jsonl')
        alias.symlink_to(self.path)
        with self.assertRaises((RuntimeError, OSError)):
            proxy.Ledger(alias, 1)

    def test_duplicate_settlement_is_rejected(self):
        ledger = self.ledger()
        ticket = self.reservation(ledger, .5)
        ledger.settle(ticket, {'usd': .1})
        with self.assertRaises(ValueError):
            ledger.settle(ticket, {'usd': .1})

    def test_write_failure_does_not_admit_request(self):
        ledger = self.ledger()
        with mock.patch.object(Path, 'open', side_effect=OSError('full test disk')):
            with self.assertRaises(OSError):
                ledger.reserve(.1)

    def test_fsync_failure_blocks_dispatch_and_restart_keeps_the_written_reservation(self):
        ledger = self.ledger()
        with mock.patch.object(proxy.os, 'fsync', side_effect=OSError('test sync failure')):
            with self.assertRaises(OSError):
                ledger.reserve(.75)
        self.assertIsNone(ledger.reserve(.1))
        ledger.close()
        self.assertIsNone(self.ledger().reserve(.5))

    def test_concurrent_reservations_cannot_exceed_the_budget(self):
        ledger = self.ledger()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            tickets = list(pool.map(lambda _: ledger.reserve(.1), range(40)))
        self.assertEqual(sum(ticket is not None for ticket in tickets), 10)
        self.assertEqual(ledger.reserved, 1)

    def test_overrun_still_blocks_after_restart(self):
        ledger = self.ledger(cap=10)
        ledger.settle(ledger.reserve(.5), {'usd': 1})
        ledger.close()
        self.assertIsNone(self.ledger(cap=10).reserve(.1))

    def test_zero_or_reused_reservation_identity_is_corrupt(self):
        histories = [
            [{'event': 'reserve', 'reservation_id': 'a', 'reserved_usd': 0}],
            [{'event': 'reserve', 'reservation_id': 'a', 'reserved_usd': .5},
             {'event': 'settle', 'reservation_id': 'a', 'usd': .1},
             {'event': 'reserve', 'reservation_id': 'a', 'reserved_usd': .5}],
        ]
        for history in histories:
            with self.subTest(history=history):
                self.path.write_text(''.join(json.dumps(row) + '\n' for row in history))
                with self.assertRaises(ValueError):
                    self.ledger()


REQUEST = {'model': 'test-model', 'messages': [{'role': 'user', 'content': 'PRIVATE_TEST_PROMPT'}]}
TEST_PRICES = {'test-model': {'flex': (1, 2), 'default': (10, 20)}}


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.payload = json.dumps({'service_tier': 'flex', 'usage': {
            'prompt_tokens': 10, 'completion_tokens': 5}, 'choices': []}).encode()
        self.error = None
        self.started, self.release = threading.Event(), threading.Event()
        self.release.set()

    def chat(self, body, timeout):
        self.calls.append(copy.deepcopy(body))
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError('fake-provider test synchronization timed out')
        if self.error is not None:
            raise self.error
        return self.status, self.payload


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.prices = mock.patch.object(proxy, 'PRICES', TEST_PRICES)
        self.prices.start()
        self.addCleanup(self.prices.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.jsonl'
        self.ledger = proxy.Ledger(self.path, 1)
        self.addCleanup(self.ledger.close)
        self.provider = FakeProvider()
        self.server = proxy.ThreadingHTTPServer(('127.0.0.1', 0),
                proxy.make_handler(self.provider, self.ledger, 'TEST_KEY', 2))
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.provider.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def post(self, body=None, *, raw=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            data = json.dumps(REQUEST if body is None else body).encode() if raw is None else raw
            connection.request('POST', '/v1/chat/completions', data,
                {'Authorization': 'Bearer TEST_KEY', 'Content-Type': 'application/json', **(headers or {})})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_default_limit_is_forwarded_and_highest_rates_are_reserved(self):
        status, _ = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(self.provider.calls[0]['max_tokens'], 4096)
        self.assertIs(self.provider.calls[0]['stream'], False)
        self.assertEqual(self.provider.calls[0]['n'], 1)
        reserve, settle = self.records()
        self.assertGreater(reserve['reserved_usd'], 4096 * 20 / 1e6)
        self.assertEqual(settle['reservation_id'], reserve['reservation_id'])
        self.assertAlmostEqual(self.ledger.spent, (10 * 1 + 5 * 2) / 1e6)
        text = self.path.read_text()
        self.assertNotIn('PRIVATE_TEST_PROMPT', text)
        self.assertNotIn('TEST_KEY', text)

    def test_alternative_positive_limit_is_forwarded_without_second_limit(self):
        status, _ = self.post(dict(REQUEST, max_completion_tokens=99))
        self.assertEqual(status, 200)
        self.assertEqual(self.provider.calls[0]['max_completion_tokens'], 99)
        self.assertNotIn('max_tokens', self.provider.calls[0])

    def test_bad_requests_never_reserve_or_dispatch(self):
        variants = [[], {}, dict(REQUEST, max_tokens=0), dict(REQUEST, max_tokens=-1),
                    dict(REQUEST, max_tokens=True), dict(REQUEST, max_tokens=1.5),
                    dict(REQUEST, max_tokens='5'), dict(REQUEST, max_tokens=None),
                    dict(REQUEST, max_tokens=1, max_completion_tokens=1),
                    dict(REQUEST, stream=True), dict(REQUEST, stream=None), dict(REQUEST, n=2),
                    dict(REQUEST, n=True), dict(REQUEST, service_tier='unpriced'), dict(REQUEST, model=[]),
                    dict(REQUEST, temperature=math.nan), dict(REQUEST, top_p=2), dict(REQUEST, seed=True),
                    dict(REQUEST, messages=[]), dict(REQUEST, messages=[{'role':'user','content': [{'type':'image'}]}]),
                    dict(REQUEST, tools=[]), dict(REQUEST, structured_outputs={'grammar':'unaccounted'})]
        for body in variants:
            with self.subTest(body=body):
                self.assertEqual(self.post(body)[0], 400)
        self.assertEqual(self.provider.calls, [])
        self.assertFalse(self.path.exists())

    def test_bad_framing_and_auth_never_dispatch(self):
        for headers, expected in (({'Content-Length': 'bad'}, 400), ({'Content-Length': '-1'}, 413),
                ({'Content-Length': str(proxy.MAX_REQUEST_BYTES + 1)}, 413),
                ({'Transfer-Encoding': 'chunked'}, 400), ({'Authorization': 'Bearer WRONG'}, 401)):
            with self.subTest(headers=headers):
                self.assertEqual(self.post(raw=b'{}', headers=headers)[0], expected)
        self.assertEqual(self.provider.calls, [])

    def test_malformed_json_never_dispatches(self):
        for raw in (b'{', b'null', b'"text"', b'\xff'):
            with self.subTest(raw=raw):
                self.assertEqual(self.post(raw=raw)[0], 400)
        self.assertEqual(self.provider.calls, [])

    def test_budget_refusal_never_dispatches(self):
        self.ledger.reserve(1)
        self.assertEqual(self.post()[0], 402)
        self.assertEqual(self.provider.calls, [])

    def test_journal_write_failure_never_dispatches(self):
        with mock.patch.object(Path, 'open', side_effect=OSError('full test disk')):
            self.assertEqual(self.post()[0], 503)
        self.assertEqual(self.provider.calls, [])
        self.assertIsNone(self.ledger.reserve(.01))

    def test_missing_and_invalid_usage_keep_the_full_reservation(self):
        variants = [{}, {'usage': {}}, {'service_tier': 'unpriced', 'usage': {'prompt_tokens': 1, 'completion_tokens':1}},
                    {'service_tier': 'flex', 'usage': {'prompt_tokens': True, 'completion_tokens':1}},
                    {'service_tier': 'flex', 'usage': {'prompt_tokens': '1', 'completion_tokens':1}},
                    {'service_tier': 'flex', 'usage': {'prompt_tokens': -1, 'completion_tokens':1}},
                    {'service_tier': 'flex', 'usage': {'prompt_tokens': 1, 'completion_tokens':math.nan}}, []]
        for body in variants:
            with self.subTest(body=body):
                self.provider.payload = json.dumps(body).encode()
                self.assertEqual(self.post()[0], 200)
                reserve, settle = self.records()[-2:]
                self.assertEqual(reserve['reserved_usd'], settle['usd'])
                self.assertEqual(settle['accounting'], 'uncertain_reserved_cost')

    def test_malformed_provider_json_keeps_the_full_reservation(self):
        self.provider.payload = b'{"usage":'
        self.assertEqual(self.post()[0], 200)
        reserve, settle = self.records()
        self.assertEqual(reserve['reserved_usd'], settle['usd'])

    def test_transport_exception_keeps_reservation_without_logging_its_contents(self):
        self.provider.error = TimeoutError('PRIVATE_TEST_PROMPT TEST_KEY')
        self.assertEqual(self.post()[0], 502)
        reserve, settle = self.records()
        self.assertEqual(reserve['reserved_usd'], settle['usd'])
        self.assertEqual(settle['error_kind'], 'TimeoutError')
        self.assertNotIn('PRIVATE_TEST_PROMPT', self.path.read_text())
        self.assertNotIn('TEST_KEY', self.path.read_text())
        self.assertEqual(len(self.provider.calls), 1)

    def test_unknown_http_outcome_keeps_reservation(self):
        self.provider.status = 500
        self.assertEqual(self.post()[0], 500)
        reserve, settle = self.records()
        self.assertEqual(reserve['reserved_usd'], settle['usd'])

    def test_observed_overrun_blocks_the_next_http_request(self):
        self.provider.payload = json.dumps({'service_tier':'default', 'usage':{
            'prompt_tokens':100000, 'completion_tokens':100000}}).encode()
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(self.post()[0], 402)
        self.assertEqual(len(self.provider.calls), 1)

    def test_inflight_request_holds_its_reservation_against_concurrent_admission(self):
        _, estimate = proxy.prepare_request(REQUEST)
        self.ledger.reserve(1 - estimate * 1.1)
        self.provider.release.clear()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.post)
            self.assertTrue(self.provider.started.wait(2))
            self.assertEqual(self.post()[0], 402)
            self.provider.release.set()
            self.assertEqual(first.result(timeout=3)[0], 200)
        self.assertEqual(len(self.provider.calls), 1)

    def test_settlement_write_failure_retains_reservation_and_blocks_admission(self):
        original = self.ledger._append
        def write(row):
            if row['event'] == 'settle':
                with mock.patch.object(Path, 'open', side_effect=OSError('full test disk')):
                    return original(row)
            return original(row)
        with mock.patch.object(self.ledger, '_append', side_effect=write):
            self.assertEqual(self.post()[0], 503)
        self.assertGreater(self.ledger.reserved, 0)
        self.assertEqual(self.post()[0], 402)
        self.assertEqual(len(self.provider.calls), 1)


class TransportTests(unittest.TestCase):
    def test_unpriced_region_is_rejected_before_authentication(self):
        with self.assertRaises(ValueError):
            proxy.Bedrock('unpriced-region', 'unused')

    def test_ambiguous_transport_and_http_failures_are_never_retried(self):
        failures = [TimeoutError('secret diagnostic'), urllib.error.URLError('lost response')]
        failures += [urllib.error.HTTPError('https://example.test', status, 'failure', {}, io.BytesIO(b'{}'))
                     for status in (429, 500, 503)]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(proxy.Bedrock, 'token', return_value='FAKE'), \
                    mock.patch.object(proxy.urllib.request, 'urlopen', side_effect=failure) as request:
                status, payload = proxy.Bedrock('us-east-1', 'unused').chat({}, 1)
                self.assertIn(status, (429, 500, 503, 504))
                self.assertEqual(request.call_count, 1)
                self.assertNotIn(b'secret diagnostic', payload)

    def test_invalid_registered_rate_prevents_estimation(self):
        with mock.patch.object(proxy, 'PRICES', {'test-model': {'flex': (1,2), 'default':(math.nan, 20)}}):
            with self.assertRaises(ValueError):
                proxy.prepare_request(REQUEST)


if __name__ == '__main__':
    unittest.main()
