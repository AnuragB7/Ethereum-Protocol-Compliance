// Package token provides ERC-20 token contract interactions
package token

import (
	"context"
	"fmt"
	"math/big"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/accounts/abi/bind"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
)

// ERC20ABI is the ABI for standard ERC-20 tokens
const ERC20ABI = `[
	{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
	{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
	{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
	{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"},
	{"constant":true,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
	{"constant":false,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
	{"constant":true,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
	{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
	{"constant":false,"inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"type":"function"},
	{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"},
	{"anonymous":false,"inputs":[{"indexed":true,"name":"owner","type":"address"},{"indexed":true,"name":"spender","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Approval","type":"event"}
]`

// TokenInfo represents basic token information
type TokenInfo struct {
	Name        string
	Symbol      string
	Decimals    uint8
	TotalSupply *big.Int
}

// TransferEvent represents an ERC-20 Transfer event
type TransferEvent struct {
	From   common.Address
	To     common.Address
	Amount *big.Int
	TxHash common.Hash
	Block  uint64
}

// TokenClient provides ERC-20 token contract interactions
type TokenClient struct {
	client          *ethclient.Client
	contractAddress common.Address
	abi             abi.ABI
	contract        *bind.BoundContract
}

// NewTokenClient creates a new token client
func NewTokenClient(client *ethclient.Client, contractAddress common.Address) (*TokenClient, error) {
	// Parse ABI
	parsedABI, err := abi.JSON(strings.NewReader(ERC20ABI))
	if err != nil {
		return nil, fmt.Errorf("failed to parse ABI: %w", err)
	}

	// Validate contract address
	if contractAddress == (common.Address{}) {
		return nil, fmt.Errorf("contract address cannot be zero address")
	}

	// Create bound contract
	contract := bind.NewBoundContract(contractAddress, parsedABI, client, client, client)

	return &TokenClient{
		client:          client,
		contractAddress: contractAddress,
		abi:             parsedABI,
		contract:        contract,
	}, nil
}

// GetTokenInfo retrieves basic token information
func (t *TokenClient) GetTokenInfo() (*TokenInfo, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	callOpts := &bind.CallOpts{Context: ctx}

	// Get name
	var name string
	err := t.contract.Call(callOpts, &[]interface{}{&name}, "name")
	if err != nil {
		return nil, fmt.Errorf("failed to get name: %w", err)
	}

	// Get symbol
	var symbol string
	err = t.contract.Call(callOpts, &[]interface{}{&symbol}, "symbol")
	if err != nil {
		return nil, fmt.Errorf("failed to get symbol: %w", err)
	}

	// Get decimals
	var decimals uint8
	err = t.contract.Call(callOpts, &[]interface{}{&decimals}, "decimals")
	if err != nil {
		return nil, fmt.Errorf("failed to get decimals: %w", err)
	}

	// Get total supply
	var totalSupply *big.Int
	err = t.contract.Call(callOpts, &[]interface{}{&totalSupply}, "totalSupply")
	if err != nil {
		return nil, fmt.Errorf("failed to get totalSupply: %w", err)
	}

	return &TokenInfo{
		Name:        name,
		Symbol:      symbol,
		Decimals:    decimals,
		TotalSupply: totalSupply,
	}, nil
}

// BalanceOf returns the token balance of an address
func (t *TokenClient) BalanceOf(address common.Address) (*big.Int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	callOpts := &bind.CallOpts{Context: ctx}

	var balance *big.Int
	err := t.contract.Call(callOpts, &[]interface{}{&balance}, "balanceOf", address)
	if err != nil {
		return nil, fmt.Errorf("failed to get balance: %w", err)
	}

	return balance, nil
}

// Allowance returns the allowance granted by owner to spender
func (t *TokenClient) Allowance(owner, spender common.Address) (*big.Int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	callOpts := &bind.CallOpts{Context: ctx}

	var allowance *big.Int
	err := t.contract.Call(callOpts, &[]interface{}{&allowance}, "allowance", owner, spender)
	if err != nil {
		return nil, fmt.Errorf("failed to get allowance: %w", err)
	}

	return allowance, nil
}

// Transfer transfers tokens to an address
func (t *TokenClient) Transfer(auth *bind.TransactOpts, to common.Address, amount *big.Int) (*types.Transaction, error) {
	// Validate recipient
	if to == (common.Address{}) {
		return nil, fmt.Errorf("cannot transfer to zero address")
	}

	// Validate amount
	if amount == nil || amount.Sign() <= 0 {
		return nil, fmt.Errorf("amount must be positive")
	}

	tx, err := t.contract.Transact(auth, "transfer", to, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to transfer: %w", err)
	}

	return tx, nil
}

// Approve approves spender to spend tokens
func (t *TokenClient) Approve(auth *bind.TransactOpts, spender common.Address, amount *big.Int) (*types.Transaction, error) {
	// Validate spender
	if spender == (common.Address{}) {
		return nil, fmt.Errorf("cannot approve zero address")
	}

	tx, err := t.contract.Transact(auth, "approve", spender, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to approve: %w", err)
	}

	return tx, nil
}

// TransferFrom transfers tokens on behalf of owner
func (t *TokenClient) TransferFrom(auth *bind.TransactOpts, from, to common.Address, amount *big.Int) (*types.Transaction, error) {
	// Validate addresses
	if from == (common.Address{}) {
		return nil, fmt.Errorf("cannot transfer from zero address")
	}
	if to == (common.Address{}) {
		return nil, fmt.Errorf("cannot transfer to zero address")
	}

	// Validate amount
	if amount == nil || amount.Sign() <= 0 {
		return nil, fmt.Errorf("amount must be positive")
	}

	tx, err := t.contract.Transact(auth, "transferFrom", from, to, amount)
	if err != nil {
		return nil, fmt.Errorf("failed to transferFrom: %w", err)
	}

	return tx, nil
}

// WatchTransfers subscribes to Transfer events
func (t *TokenClient) WatchTransfers(ctx context.Context, events chan<- *TransferEvent) error {
	// Create filter query
	query := ethereum.FilterQuery{
		Addresses: []common.Address{t.contractAddress},
		Topics:    [][]common.Hash{{t.abi.Events["Transfer"].ID}},
	}

	// Subscribe to logs
	logs := make(chan types.Log)
	sub, err := t.client.SubscribeFilterLogs(ctx, query, logs)
	if err != nil {
		return fmt.Errorf("failed to subscribe to logs: %w", err)
	}

	go func() {
		defer sub.Unsubscribe()
		for {
			select {
			case err := <-sub.Err():
				fmt.Printf("Subscription error: %v\n", err)
				return
			case log := <-logs:
				event := t.parseTransferLog(log)
				if event != nil {
					events <- event
				}
			case <-ctx.Done():
				return
			}
		}
	}()

	return nil
}

// parseTransferLog parses a Transfer event from a log
func (t *TokenClient) parseTransferLog(log types.Log) *TransferEvent {
	if len(log.Topics) < 3 {
		return nil
	}

	event := &TransferEvent{
		From:   common.HexToAddress(log.Topics[1].Hex()),
		To:     common.HexToAddress(log.Topics[2].Hex()),
		TxHash: log.TxHash,
		Block:  log.BlockNumber,
	}

	// Decode amount from data
	if len(log.Data) >= 32 {
		event.Amount = new(big.Int).SetBytes(log.Data[:32])
	}

	return event
}

// GetTransferHistory retrieves historical transfer events
func (t *TokenClient) GetTransferHistory(fromBlock, toBlock uint64) ([]*TransferEvent, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	query := ethereum.FilterQuery{
		FromBlock: big.NewInt(int64(fromBlock)),
		ToBlock:   big.NewInt(int64(toBlock)),
		Addresses: []common.Address{t.contractAddress},
		Topics:    [][]common.Hash{{t.abi.Events["Transfer"].ID}},
	}

	logs, err := t.client.FilterLogs(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to filter logs: %w", err)
	}

	events := make([]*TransferEvent, 0, len(logs))
	for _, log := range logs {
		event := t.parseTransferLog(log)
		if event != nil {
			events = append(events, event)
		}
	}

	return events, nil
}
