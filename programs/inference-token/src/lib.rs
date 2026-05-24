use anchor_lang::prelude::*;

declare_id!("INF7oken111111111111111111111111111111111");

#[program]
pub mod inference_token {
    use super::*;

    /// Initialize the inference token mint
    pub fn initialize_mint(
        ctx: Context<InitializeMint>,
        decimals: u8,
    ) -> Result<()> {
        let mint = &ctx.accounts.mint;
        let token_program = &ctx.accounts.token_program;

        // Initialize mint with freeze authority (program itself)
        let seeds = &[
            b"mint",
            &[ctx.bumps.mint],
        ];
        let signer_seeds = &[&seeds[..]];

        token::initialize_mint(
            CpiContext::new_with_signer(
                token_program.to_account_info(),
                token::InitializeMint {
                    mint: mint.to_account_info(),
                    decimals,
                    authority: Some(ctx.accounts.authority.to_account_info()),
                    freeze_authority: Some(mint.to_account_info()),
                },
                signer_seeds,
            ),
            decimals,
            &ctx.accounts.authority.key(),
        )?;

        msg!("Inference token mint initialized");
        Ok(())
    }

    /// Mint tokens to a user (requires payment or authorization)
    pub fn mint_tokens(
        ctx: Context<MintTokens>,
        amount: u64,
    ) -> Result<()> {
        let mint = &ctx.accounts.mint;
        let to_account = &ctx.accounts.to;
        let token_program = &ctx.accounts.token_program;
        let authority = &ctx.accounts.authority;

        let seeds = &[
            b"mint",
            &[ctx.bumps.mint],
        ];
        let signer_seeds = &[&seeds[..]];

        token::mint_to(
            CpiContext::new_with_signer(
                token_program.to_account_info(),
                token::MintTo {
                    mint: mint.to_account_info(),
                    to: to_account.to_account_info(),
                    authority: authority.to_account_info(),
                },
                signer_seeds,
            ),
            amount,
        )?;

        msg!("Minted {} tokens to {}", amount, to_account.key());
        Ok(())
    }

    /// Burn tokens (used for inference payments)
    pub fn burn_tokens(
        ctx: Context<BurnTokens>,
        amount: u64,
    ) -> Result<()> {
        let mint = &ctx.accounts.mint;
        let from = &ctx.accounts.from;
        let token_program = &ctx.accounts.token_program;
        let authority = &ctx.accounts.authority;

        token::burn(
            CpiContext::new(
                token_program.to_account_info(),
                token::Burn {
                    mint: mint.to_account_info(),
                    from: from.to_account_info(),
                    authority: authority.to_account_info(),
                },
            ),
            amount,
        )?;

        msg!("Burned {} tokens", amount);
        Ok(())
    }

    /// Freeze account (for governance)
    pub fn freeze_account(
        ctx: Context<FreezeAccount>,
    ) -> Result<()> {
        let mint = &ctx.accounts.mint;
        let account = &ctx.accounts.account;
        let token_program = &ctx.accounts.token_program;

        let seeds = &[
            b"mint",
            &[ctx.bumps.mint],
        ];
        let signer_seeds = &[&seeds[..]];

        token::freeze_account(
            CpiContext::new_with_signer(
                token_program.to_account_info(),
                token::FreezeAccount {
                    account: account.to_account_info(),
                    mint: mint.to_account_info(),
                    authority: mint.to_account_info(),
                },
                signer_seeds,
            ),
        )?;

        msg!("Account frozen");
        Ok(())
    }
}

#[derive(Accounts)]
pub struct InitializeMint<'info> {
    #[account(
        init,
        payer = payer,
        mint::decimals = 0,
        mint::authority = authority,
        seeds = [b"mint"],
        bump
    )]
    pub mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub authority: Signer<'info>,
    
    #[account(mut)]
    pub payer: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(
        mut,
        seeds = [b"mint"],
        bump
    )]
    pub mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub to: Account<'info, TokenAccount>,
    
    pub authority: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct BurnTokens<'info> {
    #[account(
        mut,
        seeds = [b"mint"],
        bump
    )]
    pub mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub from: Account<'info, TokenAccount>,
    
    pub authority: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct FreezeAccount<'info> {
    #[account(
        mut,
        seeds = [b"mint"],
        bump
    )]
    pub mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub account: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
}

use anchor_spl::token::{self, Mint, Token, TokenAccount};
