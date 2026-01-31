// Package wallet provides wallet management functionality
package wallet

import (
	"context"
	"crypto/ecdsa"
	"encoding/hex"
	"fmt"
	"math/big"
	"sync"

	"github.com/ethereum/go-ethereum/accounts"
	"github.com/ethereum/go-ethereum/accounts/keystore"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/crypto"
)

// Wallet represents an Ethereum wallet
type Wallet struct {
	Address    common.Address
	PrivateKey *ecdsa.PrivateKey
	PublicKey  *ecdsa.PublicKey
}

// WalletService manages multiple wallets
type WalletService struct {
	keystore *keystore.KeyStore
	wallets  map[common.Address]*Wallet
	mu       sync.RWMutex
}

// NewWalletService creates a new wallet service
func NewWalletService(keystorePath string) (*WalletService, error) {
	ks := keystore.NewKeyStore(keystorePath, keystore.StandardScryptN, keystore.StandardScryptP)
	
	return &WalletService{
		keystore: ks,
		wallets:  make(map[common.Address]*Wallet),
	}, nil
}

// CreateWallet creates a new wallet with a passphrase
func (ws *WalletService) CreateWallet(passphrase string) (*Wallet, error) {
	// Generate new private key
	privateKey, err := crypto.GenerateKey()
	if err != nil {
		return nil, fmt.Errorf("failed to generate private key: %w", err)
	}

	// Derive public key and address
	publicKey := privateKey.Public()
	publicKeyECDSA, ok := publicKey.(*ecdsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("failed to derive public key")
	}
	address := crypto.PubkeyToAddress(*publicKeyECDSA)

	// Store in keystore
	account, err := ws.keystore.ImportECDSA(privateKey, passphrase)
	if err != nil {
		return nil, fmt.Errorf("failed to import to keystore: %w", err)
	}

	wallet := &Wallet{
		Address:    account.Address,
		PrivateKey: privateKey,
		PublicKey:  publicKeyECDSA,
	}

	// Store in memory
	ws.mu.Lock()
	ws.wallets[address] = wallet
	ws.mu.Unlock()

	return wallet, nil
}

// ImportWallet imports a wallet from a private key hex string
func (ws *WalletService) ImportWallet(privateKeyHex, passphrase string) (*Wallet, error) {
	// Remove 0x prefix if present
	if len(privateKeyHex) >= 2 && privateKeyHex[:2] == "0x" {
		privateKeyHex = privateKeyHex[2:]
	}

	// Validate hex
	if len(privateKeyHex) != 64 {
		return nil, fmt.Errorf("invalid private key length")
	}

	// Parse private key
	privateKey, err := crypto.HexToECDSA(privateKeyHex)
	if err != nil {
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	// Derive public key and address
	publicKey := privateKey.Public()
	publicKeyECDSA, ok := publicKey.(*ecdsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("failed to derive public key")
	}
	address := crypto.PubkeyToAddress(*publicKeyECDSA)

	// Store in keystore
	_, err = ws.keystore.ImportECDSA(privateKey, passphrase)
	if err != nil {
		return nil, fmt.Errorf("failed to import to keystore: %w", err)
	}

	wallet := &Wallet{
		Address:    address,
		PrivateKey: privateKey,
		PublicKey:  publicKeyECDSA,
	}

	// Store in memory
	ws.mu.Lock()
	ws.wallets[address] = wallet
	ws.mu.Unlock()

	return wallet, nil
}

// UnlockWallet unlocks a wallet from the keystore
func (ws *WalletService) UnlockWallet(address common.Address, passphrase string) (*Wallet, error) {
	// Find account in keystore
	account := accounts.Account{Address: address}

	// Unlock account
	err := ws.keystore.Unlock(account, passphrase)
	if err != nil {
		return nil, fmt.Errorf("failed to unlock wallet: %w", err)
	}

	// Get private key (requires unlocked account)
	keyJSON, err := ws.keystore.Export(account, passphrase, passphrase)
	if err != nil {
		return nil, fmt.Errorf("failed to export key: %w", err)
	}

	key, err := keystore.DecryptKey(keyJSON, passphrase)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt key: %w", err)
	}

	wallet := &Wallet{
		Address:    address,
		PrivateKey: key.PrivateKey,
		PublicKey:  &key.PrivateKey.PublicKey,
	}

	// Store in memory
	ws.mu.Lock()
	ws.wallets[address] = wallet
	ws.mu.Unlock()

	return wallet, nil
}

// GetWallet returns a wallet by address
func (ws *WalletService) GetWallet(address common.Address) (*Wallet, error) {
	ws.mu.RLock()
	defer ws.mu.RUnlock()

	wallet, ok := ws.wallets[address]
	if !ok {
		return nil, fmt.Errorf("wallet not found: %s", address.Hex())
	}

	return wallet, nil
}

// ListWallets returns all managed wallet addresses
func (ws *WalletService) ListWallets() []common.Address {
	ws.mu.RLock()
	defer ws.mu.RUnlock()

	addresses := make([]common.Address, 0, len(ws.wallets))
	for addr := range ws.wallets {
		addresses = append(addresses, addr)
	}

	return addresses
}

// SignMessage signs a message with a wallet's private key
func (ws *WalletService) SignMessage(address common.Address, message []byte) ([]byte, error) {
	wallet, err := ws.GetWallet(address)
	if err != nil {
		return nil, err
	}

	// Hash the message with Ethereum prefix
	hash := crypto.Keccak256Hash(
		[]byte(fmt.Sprintf("\x19Ethereum Signed Message:\n%d%s", len(message), message)),
	)

	// Sign the hash
	signature, err := crypto.Sign(hash.Bytes(), wallet.PrivateKey)
	if err != nil {
		return nil, fmt.Errorf("failed to sign message: %w", err)
	}

	return signature, nil
}

// VerifySignature verifies a message signature
func VerifySignature(address common.Address, message, signature []byte) (bool, error) {
	if len(signature) != 65 {
		return false, fmt.Errorf("invalid signature length")
	}

	// Hash the message with Ethereum prefix
	hash := crypto.Keccak256Hash(
		[]byte(fmt.Sprintf("\x19Ethereum Signed Message:\n%d%s", len(message), message)),
	)

	// Recover the public key
	sig := make([]byte, 65)
	copy(sig, signature)
	if sig[64] >= 27 {
		sig[64] -= 27
	}

	publicKey, err := crypto.SigToPub(hash.Bytes(), sig)
	if err != nil {
		return false, fmt.Errorf("failed to recover public key: %w", err)
	}

	// Derive address from recovered public key
	recoveredAddress := crypto.PubkeyToAddress(*publicKey)

	return recoveredAddress == address, nil
}

// ExportPrivateKey exports the private key as hex string (DANGEROUS!)
func (w *Wallet) ExportPrivateKey() string {
	return hex.EncodeToString(crypto.FromECDSA(w.PrivateKey))
}

// GetPublicKeyHex returns the public key as hex string
func (w *Wallet) GetPublicKeyHex() string {
	return hex.EncodeToString(crypto.FromECDSAPub(w.PublicKey))
}

// ValidateAddress checks if a string is a valid Ethereum address
func ValidateAddress(addressStr string) bool {
	return common.IsHexAddress(addressStr)
}

// AddressFromPrivateKey derives address from private key hex
func AddressFromPrivateKey(privateKeyHex string) (common.Address, error) {
	if len(privateKeyHex) >= 2 && privateKeyHex[:2] == "0x" {
		privateKeyHex = privateKeyHex[2:]
	}

	privateKey, err := crypto.HexToECDSA(privateKeyHex)
	if err != nil {
		return common.Address{}, fmt.Errorf("invalid private key: %w", err)
	}

	publicKey := privateKey.Public()
	publicKeyECDSA, ok := publicKey.(*ecdsa.PublicKey)
	if !ok {
		return common.Address{}, fmt.Errorf("failed to derive public key")
	}

	return crypto.PubkeyToAddress(*publicKeyECDSA), nil
}
