from __future__ import annotations

import copy
import json
import uuid
from typing import TYPE_CHECKING, Sequence, Type

from . import Keypair
from . import xdr as stellar_xdr
from .account import Account
from .address import Address
from .client.requests_client import RequestsClient
from .exceptions import (
    AccountNotFoundException,
    PrepareTransactionException,
    SorobanRpcErrorResponse,
)
from .operation import InvokeHostFunction
from .soroban_rpc import *

if TYPE_CHECKING:
    from .client.base_sync_client import BaseSyncClient
    from .transaction_envelope import TransactionEnvelope

__all__ = ["SorobanServer"]

V = TypeVar("V")


class Durability(Enum):
    TEMPORARY = "temporary"
    PERSISTENT = "persistent"


class SorobanServer:
    """Server handles the network connection to a Soroban RPC instance and
    exposes an interface for requests to that instance.

    :param server_url: Soroban RPC server URL. (ex. ``https://rpc-futurenet.stellar.org:443/``)
    :param client: A client instance that will be used to make requests.
    """

    def __init__(
        self,
        server_url: str = "https://rpc-futurenet.stellar.org:443/",
        client: Optional[BaseSyncClient] = None,
    ) -> None:
        self.server_url: str = server_url

        if not client:
            client = RequestsClient()
        self._client: BaseSyncClient = client

    def get_health(self) -> GetHealthResponse:
        """General node health check.

        See `Soroban Documentation - getHealth <https://soroban.stellar.org/api/methods/getHealth>`_

        :return: A :class:`GetHealthResponse <stellar_sdk.soroban_rpc.GetHealthResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        request: Request = Request(
            id=_generate_unique_request_id(),
            method="getHealth",
            params=None,
        )
        return self._post(request, GetHealthResponse)

    def get_events(
        self,
        start_ledger: int,
        filters: Sequence[EventFilter] = None,
        cursor: str = None,
        limit: int = None,
    ) -> GetEventsResponse:
        """Fetch a list of events that occurred in the ledger range.

        See `Soroban Documentation - getEvents <https://soroban.stellar.org/api/methods/getEvents>`_

        :param start_ledger: The first ledger to include in the results.
        :param filters: A list of filters to apply to the results.
        :param cursor: A cursor value for use in pagination.
        :param limit: The maximum number of records to return.
        :return: A :class:`GetEventsResponse <stellar_sdk.soroban_rpc.GetEventsResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        pagination = PaginationOptions(cursor=cursor, limit=limit)
        data = GetEventsRequest(
            startLedger=str(start_ledger),
            filters=filters,
            pagination=pagination,
        )
        request: Request = Request[GetEventsRequest](
            id=_generate_unique_request_id(), method="getEvents", params=data
        )
        return self._post(request, GetEventsResponse)

    def get_network(self) -> GetNetworkResponse:
        """General info about the currently configured network.

        :return: A :class:`GetNetworkResponse <stellar_sdk.soroban_rpc.GetNetworkResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        request: Request = Request(
            id=_generate_unique_request_id(),
            method="getNetwork",
            params=None,
        )
        return self._post(request, GetNetworkResponse)

    def get_latest_ledger(self) -> GetLatestLedgerResponse:
        """Fetches the latest ledger meta info from network which Soroban-RPC is connected to.

        :return: A :class:`GetLatestLedgerResponse <stellar_sdk.soroban_rpc.GetLatestLedgerResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        request: Request = Request(
            id=_generate_unique_request_id(),
            method="getLatestLedger",
            params=None,
        )
        return self._post(request, GetLatestLedgerResponse)

    def get_ledger_entries(
        self, keys: List[stellar_xdr.LedgerKey]
    ) -> GetLedgerEntriesResponse:
        """For reading the current value of ledger entries directly.

        Allows you to directly inspect the current state of a contract, a contract's code,
        or any other ledger entry. This is a backup way to access your contract data
        which may not be available via events or simulateTransaction.

        See `Soroban Documentation - getLedgerEntries <https://soroban.stellar.org/api/methods/getLedgerEntries>`_

        :param keys: The ledger keys to fetch.
        :return: A :class:`GetLedgerEntriesResponse <stellar_sdk.soroban_rpc.GetLedgerEntryResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        request = Request[GetLedgerEntriesRequest](
            id=_generate_unique_request_id(),
            method="getLedgerEntries",
            params=GetLedgerEntriesRequest(keys=[key.to_xdr() for key in keys]),
        )
        return self._post(request, GetLedgerEntriesResponse)

    def get_transaction(self, transaction_hash: str) -> GetTransactionResponse:
        """Fetch the specified transaction.

        See `Soroban Documentation - getTransaction <https://soroban.stellar.org/api/methods/getTransaction>`_

        :param transaction_hash: The hash of the transaction to fetch.
        :return: A :class:`GetTransactionResponse <stellar_sdk.soroban_rpc.GetTransactionResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        request = Request[GetTransactionRequest](
            id=_generate_unique_request_id(),
            method="getTransaction",
            params=GetTransactionRequest(hash=transaction_hash),
        )
        return self._post(request, GetTransactionResponse)

    def simulate_transaction(
        self, transaction_envelope: TransactionEnvelope
    ) -> SimulateTransactionResponse:
        """Submit a trial contract invocation to get back return values, expected ledger footprint, and expected costs.

        See `Soroban Documentation - simulateTransaction <https://soroban.stellar.org/api/methods/simulateTransaction>`_

        :param transaction_envelope: The transaction to simulate. It should include exactly one operation,
            which must be one of :class:`RestoreFootprint <stellar_sdk.operation.RestoreFootprintOperation>`,
            :class:`InvokeHostFunction <stellar_sdk.operation.InvokeHostFunction>` or
            :class:`BumpFootprintExpiration <stellar_sdk.operation.RestoreFootprint>` operation.
            Any provided footprint will be ignored.
        :return: A :class:`SimulateTransactionResponse <stellar_sdk.soroban_rpc.SimulateTransactionResponse>` object
            contains the cost, footprint, result/auth requirements (if applicable), and error of the transaction.
        """
        xdr = (
            transaction_envelope
            if isinstance(transaction_envelope, str)
            else transaction_envelope.to_xdr()
        )
        request = Request[SimulateTransactionRequest](
            id=_generate_unique_request_id(),
            method="simulateTransaction",
            params=SimulateTransactionRequest(transaction=xdr),
        )
        return self._post(request, SimulateTransactionResponse)

    def send_transaction(
        self, transaction_envelope: Union[TransactionEnvelope, str]
    ) -> SendTransactionResponse:
        """Submit a real transaction to the Stellar network. This is the only way to make changes "on-chain".

        See `Soroban Documentation - sendTransaction <https://soroban.stellar.org/api/methods/sendTransaction>`_

        :param transaction_envelope: The transaction to send.
        :return: A :class:`SendTransactionResponse <stellar_sdk.soroban_rpc.SendTransactionResponse>` object.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        xdr = (
            transaction_envelope
            if isinstance(transaction_envelope, str)
            else transaction_envelope.to_xdr()
        )
        request = Request[SendTransactionRequest](
            id=_generate_unique_request_id(),
            method="sendTransaction",
            params=SendTransactionRequest(transaction=xdr),
        )
        return self._post(request, SendTransactionResponse)

    def load_account(self, account_id: str) -> Account:
        """Load an account from the server, you can use the returned account
        object as source account for transactions.

        :param account_id: The account ID.
        :return: An :class:`Account <stellar_sdk.account.Account>` object.
        :raises: :exc:`AccountNotFoundException <stellar_sdk.exceptions.AccountNotFoundException>` - If the account is not found on the network.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        account_id_xdr = Keypair.from_public_key(account_id).xdr_account_id()
        key = stellar_xdr.LedgerKey(
            stellar_xdr.LedgerEntryType.ACCOUNT,
            account=stellar_xdr.LedgerKeyAccount(account_id=account_id_xdr),
        )

        resp = self.get_ledger_entries([key])
        if not resp.entries:
            raise AccountNotFoundException(account_id)
        assert len(resp.entries) == 1
        data = stellar_xdr.LedgerEntryData.from_xdr(resp.entries[0].xdr)
        assert data.account is not None
        return Account(account_id, data.account.seq_num.sequence_number.int64)

    def get_contract_data(
        self,
        contract_id: str,
        key: stellar_xdr.SCVal,
        durability: Durability = Durability.PERSISTENT,
    ) -> Optional[LedgerEntryResult]:
        """Reads the current value of contract data ledger entries directly.

        :param contract_id: The contract ID containing the data to load. Encoded as Stellar Contract Address,
            for example: ``"CCJZ5DGASBWQXR5MPFCJXMBI333XE5U3FSJTNQU7RIKE3P5GN2K2WYD5"``
        :param key: The key of the contract data to load.
        :param durability: The "durability keyspace" that this ledger key belongs to, which is either
            :class:`Durability.TEMPORARY` or :class:`Durability.PERSISTENT`. Defaults to :class:`Durability.PERSISTENT`.
        :return: A :class:`LedgerEntryResult <stellar_sdk.soroban_rpc.LedgerEntryResult>` object contains the ledger entry result or ``None`` if not found.
        :raises: :exc:`SorobanRpcErrorResponse <stellar_sdk.exceptions.SorobanRpcErrorResponse>` - If the Soroban-RPC instance returns an error response.
        """
        sc_address = Address(contract_id).to_xdr_sc_address()
        xdr_durability = (
            stellar_xdr.ContractDataDurability.PERSISTENT
            if durability == Durability.PERSISTENT
            else stellar_xdr.ContractDataDurability.TEMPORARY
        )
        contract_key = stellar_xdr.LedgerKey(
            stellar_xdr.LedgerEntryType.CONTRACT_DATA,
            contract_data=stellar_xdr.LedgerKeyContractData(
                contract=sc_address,
                key=key,
                durability=xdr_durability,
            ),
        )
        resp = self.get_ledger_entries([contract_key])
        entries = resp.entries
        if not entries:
            return None
        return entries[0]

    def prepare_transaction(
        self,
        transaction_envelope: TransactionEnvelope,
    ) -> TransactionEnvelope:
        """Submit a trial contract invocation, first run a simulation of the contract
        invocation as defined on the incoming transaction, and apply the results to
        a new copy of the transaction which is then returned. Setting the ledger
        footprint and authorization, so the resulting transaction is ready for signing
        and sending.

        The returned transaction will also have an updated fee that is the sum of fee
        set on incoming transaction with the contract resource fees estimated from
        simulation. It is advisable to check the fee on returned transaction and validate
        or take appropriate measures for interaction with user to confirm it is acceptable.

        You can call the :meth:`simulate_transaction` method directly first if you
        want to inspect estimated fees for a given transaction in detail first if that is
        of importance.

        :param transaction_envelope: The transaction to prepare. It should include exactly one operation, which
            must be one of :py:class:`RestoreFootprint <stellar_sdk.operation.RestoreFootprint>`,
            :py:class:`BumpFootprintExpiration <stellar_sdk.operation.BumpFootprintExpiration>`,
            or :py:class:`InvokeHostFunction <stellar_sdk.operation.InvokeHostFunction>`. Any provided
            footprint will be ignored. You can use :meth:`stellar_sdk.Transaction.is_soroban_transaction` to check
            if a transaction is a Soroban transaction. Any provided footprint will be overwritten.
            However, if your operation has existing auth entries, they will be preferred over ALL auth
            entries from the simulation. In other words, if you include auth entries, you don't care
            about the auth returned from the simulation. Other fields (footprint, etc.) will be filled
            as normal.
        :return: A copy of the :class:`TransactionEnvelope <stellar_sdk.transaction_envelope.TransactionEnvelope>`,
            with the expected authorizations (in the case of invocation) and ledger footprint added.
            The transaction fee will also automatically be padded with the contract's minimum resource fees
            discovered from the simulation.
        """
        resp = self.simulate_transaction(transaction_envelope)
        if resp.error:
            raise PrepareTransactionException(
                "Simulation transaction failed, the response contains error information.",
                resp,
            )
        te = _assemble_transaction(transaction_envelope, resp)
        return te

    def close(self) -> None:
        """Close underlying connector, and release all acquired resources."""
        self._client.close()

    def _post(self, request_body: Request, response_body_type: Type[V]) -> V:
        json_data = request_body.model_dump_json(by_alias=True)
        data = self._client.post(
            self.server_url,
            json_data=json.loads(json_data),
        )
        response = Response[response_body_type].model_validate(data.json())  # type: ignore[valid-type]
        if response.error:
            raise SorobanRpcErrorResponse(
                response.error.code, response.error.message, response.error.data
            )
        return response.result  # type: ignore[return-value]

    def __enter__(self) -> "SorobanServer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __str__(self):
        return f"<SorobanServer [server_url={self.server_url}, client={self._client}]>"


def _generate_unique_request_id() -> str:
    return uuid.uuid4().hex


def _assemble_transaction(
    transaction_envelope: TransactionEnvelope,
    simulation: SimulateTransactionResponse,
) -> TransactionEnvelope:
    # TODO: add support for FeeBumpTransactionEnvelope
    if not transaction_envelope.transaction.is_soroban_transaction():
        raise ValueError(
            "Unsupported transaction: must contain exactly one operation of "
            "type RestoreFootprint, InvokeHostFunction or BumpFootprintExpiration"
        )

    min_resource_fee = simulation.min_resource_fee
    assert simulation.transaction_data is not None
    soroban_data = stellar_xdr.SorobanTransactionData.from_xdr(
        simulation.transaction_data
    )
    te = copy.deepcopy(transaction_envelope)
    te.signatures = []
    assert min_resource_fee is not None
    te.transaction.fee += min_resource_fee
    te.transaction.soroban_data = soroban_data

    op = te.transaction.operations[0]

    if isinstance(op, InvokeHostFunction):
        if not simulation.results or len(simulation.results) != 1:
            raise ValueError(f"Simulation results invalid: {simulation.results}")

        if not op.auth and simulation.results[0].auth:
            op.auth = [
                stellar_xdr.SorobanAuthorizationEntry.from_xdr(xdr)
                for xdr in simulation.results[0].auth
            ]
    return te
