#!/usr/bin/env python3
# Copyright (c) 2025 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test how the wallet deals with v3 transactions"""

from decimal import Decimal, getcontext

from test_framework.authproxy import JSONRPCException
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_greater_than,
    assert_raises_rpc_error,
)

def cleanup(func):
    def wrapper(self):
        try:
            func(self)
        finally:
            self.generate(self.nodes[0], 1)
            try:
                self.alice.sendall([self.charlie.getnewaddress()])
            except JSONRPCException as e:
                assert "Total value of UTXO pool too low to pay for transaction" in e.error['message']
            try:
                self.bob.sendall([self.charlie.getnewaddress()])
            except JSONRPCException as e:
                assert "Total value of UTXO pool too low to pay for transaction" in e.error['message']
            self.sync_mempools()
            self.generate(self.nodes[0], 1)
            assert_equal(0, self.alice.getbalances()["mine"]["untrusted_pending"])
            assert_equal(0, self.bob.getbalances()["mine"]["untrusted_pending"])
            assert_equal(50, self.alice.getbalances()["mine"]["trusted"])
            assert_equal(0, self.bob.getbalances()["mine"]["trusted"])
            assert_equal(0, self.bob.getbalances()["mine"]["immature"])
            assert_equal(self.alice.getrawmempool(), [])
            assert_equal(self.bob.getrawmempool(), [])

    return wrapper

class WalletV3Test(BitcoinTestFramework):
    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def set_test_params(self):
        getcontext().prec=10
        self.num_nodes = 3
        self.setup_clean_chain = True

    def run_test(self):
        self.connect_nodes(0, 1)

        self.nodes[0].createwallet("alice")
        self.alice = self.nodes[0].get_wallet_rpc("alice")

        self.nodes[1].createwallet("bob")
        self.bob = self.nodes[1].get_wallet_rpc("bob")

        self.nodes[2].createwallet("charlie")
        self.charlie = self.nodes[2].get_wallet_rpc("charlie")

        self.generatetoaddress(self.nodes[0], 100, self.alice.getnewaddress())

        self.v3_tx_spends_unconfirmed_v2_tx()
        self.v3_utxos_appear_in_listunspent()

    @cleanup
    def v3_tx_spends_unconfirmed_v2_tx(self):
        self.log.info("Test unavailable funds when v3 tx spends unconfirmed v2 tx")

        self.generate(self.nodes[0], 1)
        assert_equal(self.alice.getbalances()["mine"]["trusted"], 50)

        # by default, sendall uses tx version 2
        self.alice.sendall([self.bob.getnewaddress()])
        assert_equal(self.alice.getbalances()["mine"]["trusted"], 0)

        self.sync_mempools()

        assert_equal(self.bob.getbalances()["mine"]["trusted"], 0)
        assert_greater_than(self.bob.getbalances()["mine"]["untrusted_pending"], 49)

        inputs = []
        outputs = {self.alice.getnewaddress() : 1.0}

        raw_tx_v3 = self.bob.createrawtransaction(inputs=inputs, outputs=outputs, version=3)

        assert_raises_rpc_error(
            -4,
            "Insufficient funds",
            self.bob.fundrawtransaction,
            raw_tx_v3, {'include_unsafe': True}
        )

    @cleanup
    def v3_utxos_appear_in_listunspent(self):
        self.log.info("Test that unconfirmed v3 utxos still appear in listunspent")

        inputs=[]
        outputs = {self.bob.getnewaddress() : 2.0, self.alice.getnewaddress() : 2.0}
        parent_tx = self.alice.createrawtransaction(inputs=inputs, outputs=outputs, version=3)
        parent_tx = self.alice.fundrawtransaction(parent_tx)
        parent_tx = self.alice.signrawtransactionwithwallet(parent_tx["hex"])
        parent_tx = self.alice.sendrawtransaction(parent_tx["hex"])
        self.sync_mempools()
        assert_equal(self.bob.listunspent(minconf=0)[0]["txid"], parent_tx)

if __name__ == '__main__':
    WalletV3Test(__file__).main()
