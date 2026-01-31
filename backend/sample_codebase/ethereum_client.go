// Package ethereum provides Ethereum blockchain interaction utilities
package ethereum

import (
	"context"
	"crypto/ecdsa"
	"fmt"
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/accounts/abi/bind"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
)

// EthereumClient wraps the go-ethereum client with additional functionality
type EthereumClient struct {
	client     *ethclient.Client
	chainID    *big.Int
	privateKey *ecdsa.PrivateKey
	address    common.Address
}

// Config holds the configuration for EthereumClient
type Config struct {
	RpcURL     string
	PrivateKey string
	ChainID    int64
}

// NewEthereumClient creates a new Ethereum client connection
func NewEthereumClient(cfg Config) (*EthereumClient, error) {
	// Connect to Ethereum node
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	client, err := ethclient.DialContext(ctx, cfg.RpcURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Ethereum node: %w", err)
	}

	// Parse private key
	privateKey, err := crypto.HexToECDSA(cfg.PrivateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	// Derive address from private key
	publicKey := privateKey.Public()
	publicKeyECDSA, ok := publicKey.(*ecdsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("failed to get public key")
	}
	address := crypto.PubkeyToAddress(*publicKeyECDSA)

	return &EthereumClient{
		client:     client,
		chainID:    big.NewInt(cfg.ChainID),
		privateKey: privateKey,
		address:    address,
	}, nil
}

// Close closes the client connection
func (e *EthereumClient) Close() {
	e.client.Close()
}

// GetBalance returns the balance of an address in wei
func (e *EthereumClient) GetBalance(address common.Address) (*big.Int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	balance, err := e.client.BalanceAt(ctx, address, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get balance: %w", err)
	}

	return balance, nil
}

// SendETH sends ETH to a recipient address
func (e *EthereumClient) SendETH(to common.Address, amount *big.Int) (*types.Transaction, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Get pending nonce
	nonce, err := e.client.PendingNonceAt(ctx, e.address)
	if err != nil {
		return nil, fmt.Errorf("failed to get nonce: %w", err)
	}

	// Get suggested gas price
	gasPrice, err := e.client.SuggestGasPrice(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get gas price: %w", err)
	}

	// Create transaction
	gasLimit := uint64(21000) // Standard ETH transfer
	tx := types.NewTransaction(nonce, to, amount, gasLimit, gasPrice, nil)

	// Sign transaction
	signedTx, err := types.SignTx(tx, types.NewEIP155Signer(e.chainID), e.privateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to sign transaction: %w", err)
	}

	// Send transaction
	err = e.client.SendTransaction(ctx, signedTx)
	if err != nil {
		return nil, fmt.Errorf("failed to send transaction: %w", err)
	}

	return signedTx, nil
}

// WaitForTransaction waits for a transaction to be mined
func (e *EthereumClient) WaitForTransaction(tx *types.Transaction) (*types.Receipt, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	receipt, err := bind.WaitMined(ctx, e.client, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to wait for transaction: %w", err)
	}

	if receipt.Status == 0 {
		return nil, fmt.Errorf("transaction failed")
	}

	return receipt, nil
}

// EstimateGas estimates the gas required for a transaction
func (e *EthereumClient) EstimateGas(to common.Address, data []byte) (uint64, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	msg := ethereum.CallMsg{
		From: e.address,
		To:   &to,
		Data: data,
	}

	gasLimit, err := e.client.EstimateGas(ctx, msg)
	if err != nil {
		return 0, fmt.Errorf("failed to estimate gas: %w", err)
	}

	return gasLimit, nil
}

// GetBlockNumber returns the current block number
func (e *EthereumClient) GetBlockNumber() (uint64, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	blockNumber, err := e.client.BlockNumber(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to get block number: %w", err)
	}

	return blockNumber, nil
}

// ProcessBlocks processes blocks in a range asynchronously
func (e *EthereumClient) ProcessBlocks(start, end uint64, processor func(*types.Block) error) error {
	results := make(chan error, end-start+1)

	for i := start; i <= end; i++ {
		go func(blockNum uint64) {
			block, err := e.getBlockByNumber(blockNum)
			if err != nil {
				results <- err
				return
			}
			results <- processor(block)
		}(i)
	}

	// Collect results
	for i := start; i <= end; i++ {
		if err := <-results; err != nil {
			return err
		}
	}

	return nil
}

// getBlockByNumber retrieves a block by its number
func (e *EthereumClient) getBlockByNumber(number uint64) (*types.Block, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	block, err := e.client.BlockByNumber(ctx, big.NewInt(int64(number)))
	if err != nil {
		return nil, fmt.Errorf("failed to get block %d: %w", number, err)
	}

	return block, nil
}
