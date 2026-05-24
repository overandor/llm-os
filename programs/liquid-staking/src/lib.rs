use anchor_lang::prelude::*;

declare_id!("LStk1111111111111111111111111111111111111");

#[program]
pub mod liquid_staking {
    use super::*;

    /// Initialize the liquid staking pool
    pub fn initialize_pool(
        ctx: Context<InitializePool>,
        reward_rate: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        pool.authority = ctx.accounts.authority.key();
        pool.staked_token_mint = ctx.accounts.staked_token_mint.key();
        pool.reward_token_mint = ctx.accounts.reward_token_mint.key();
        pool.staked_amount = 0;
        pool.reward_rate = reward_rate;
        pool.last_update_timestamp = Clock::get()?.unix_timestamp;
        pool.bump = ctx.bumps.pool;

        msg!("Liquid staking pool initialized with reward rate: {}", reward_rate);
        Ok(())
    }

    /// Stake tokens
    pub fn stake(
        ctx: Context<Stake>,
        amount: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;

        // Update rewards
        update_rewards(pool, user_stake)?;

        // Transfer staked tokens from user to pool
        let seeds = &[
            b"pool",
            pool.staked_token_mint.as_ref(),
            &[pool.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = token::Transfer {
            from: ctx.accounts.user_token_account.to_account_info(),
            to: ctx.accounts.pool_token_account.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, amount)?;

        // Update user stake
        user_stake.amount += amount;
        user_stake.last_update_timestamp = Clock::get()?.unix_timestamp;

        // Update pool
        pool.staked_amount += amount;

        msg!("Staked {} tokens", amount);
        Ok(())
    }

    /// Unstake tokens
    pub fn unstake(
        ctx: Context<Unstake>,
        amount: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;

        // Update rewards
        update_rewards(pool, user_stake)?;

        // Check sufficient stake
        require!(user_stake.amount >= amount, StakingError::InsufficientStake);

        // Transfer tokens back to user
        let seeds = &[
            b"pool",
            pool.staked_token_mint.as_ref(),
            &[pool.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = token::Transfer {
            from: ctx.accounts.pool_token_account.to_account_info(),
            to: ctx.accounts.user_token_account.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer_seeds);
        token::transfer(cpi_ctx, amount)?;

        // Update user stake
        user_stake.amount -= amount;
        user_stake.last_update_timestamp = Clock::get()?.unix_timestamp;

        // Update pool
        pool.staked_amount -= amount;

        msg!("Unstaked {} tokens", amount);
        Ok(())
    }

    /// Claim rewards
    pub fn claim_rewards(
        ctx: Context<ClaimRewards>,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;

        // Update rewards
        update_rewards(pool, user_stake)?;

        let rewards = user_stake.pending_rewards;
        require!(rewards > 0, StakingError::NoRewards);

        // Mint reward tokens to user
        let seeds = &[
            b"pool",
            pool.staked_token_mint.as_ref(),
            &[pool.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = token::MintTo {
            mint: ctx.accounts.reward_token_mint.to_account_info(),
            to: ctx.accounts.user_reward_account.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer_seeds);
        token::mint_to(cpi_ctx, rewards)?;

        // Reset pending rewards
        user_stake.pending_rewards = 0;

        msg!("Claimed {} reward tokens", rewards);
        Ok(())
    }

    /// Update reward rate (authority only)
    pub fn update_reward_rate(
        ctx: Context<UpdateRewardRate>,
        new_rate: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        // Update rewards before changing rate
        let current_time = Clock::get()?.unix_timestamp;
        let time_elapsed = current_time - pool.last_update_timestamp;
        
        if pool.staked_amount > 0 && time_elapsed > 0 {
            let rewards = pool.staked_amount
                .checked_mul(pool.reward_rate)
                .ok_or(StakingError::MathOverflow)?
                .checked_div(86400) // Per day
                .ok_or(StakingError::MathOverflow)?
                .checked_mul(time_elapsed as u64)
                .ok_or(StakingError::MathOverflow)?
                .checked_div(86400)
                .ok_or(StakingError::MathOverflow)?;
            
            pool.pending_rewards = pool.pending_rewards.checked_add(rewards).ok_or(StakingError::MathOverflow)?;
        }

        pool.reward_rate = new_rate;
        pool.last_update_timestamp = current_time;

        msg!("Reward rate updated to {}", new_rate);
        Ok(())
    }
}

fn update_rewards(pool: &mut Account<Pool>, user_stake: &mut Account<UserStake>) -> Result<()> {
    let current_time = Clock::get()?.unix_timestamp;
    let time_elapsed = current_time - user_stake.last_update_timestamp;

    if user_stake.amount > 0 && time_elapsed > 0 {
        let user_rewards = user_stake.amount
            .checked_mul(pool.reward_rate)
            .ok_or(StakingError::MathOverflow)?
            .checked_div(86400) // Per day
            .ok_or(StakingError::MathOverflow)?
            .checked_mul(time_elapsed as u64)
            .ok_or(StakingError::MathOverflow)?
            .checked_div(86400)
            .ok_or(StakingError::MathOverflow)?;

        user_stake.pending_rewards = user_stake.pending_rewards
            .checked_add(user_rewards)
            .ok_or(StakingError::MathOverflow)?;
    }

    user_stake.last_update_timestamp = current_time;
    Ok(())
}

#[account]
pub struct Pool {
    pub authority: Pubkey,
    pub staked_token_mint: Pubkey,
    pub reward_token_mint: Pubkey,
    pub staked_amount: u64,
    pub reward_rate: u64, // Rewards per day per token (scaled)
    pub pending_rewards: u64,
    pub last_update_timestamp: i64,
    pub bump: u8,
}

#[account]
pub struct UserStake {
    pub owner: Pubkey,
    pub amount: u64,
    pub pending_rewards: u64,
    pub last_update_timestamp: i64,
}

#[derive(Accounts)]
pub struct InitializePool<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + 32 + 32 + 32 + 8 + 8 + 8 + 8 + 1,
        seeds = [b"pool", staked_token_mint.key().as_ref()],
        bump
    )]
    pub pool: Account<'info, Pool>,
    
    pub staked_token_mint: Account<'info, Mint>,
    pub reward_token_mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub authority: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.staked_token_mint.as_ref()],
        bump = pool.bump
    )]
    pub pool: Account<'info, Pool>,
    
    #[account(
        init_if_needed,
        payer = user,
        space = 8 + 32 + 8 + 8 + 8,
        seeds = [b"user_stake", user.key().as_ref(), pool.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,
    
    #[account(
        mut,
        constraint = user_token_account.mint == pool.staked_token_mint
    )]
    pub user_token_account: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = pool_token_account.mint == pool.staked_token_mint
    )]
    pub pool_token_account: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.staked_token_mint.as_ref()],
        bump = pool.bump
    )]
    pub pool: Account<'info, Pool>,
    
    #[account(
        mut,
        seeds = [b"user_stake", user.key().as_ref(), pool.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,
    
    #[account(
        mut,
        constraint = user_token_account.mint == pool.staked_token_mint
    )]
    pub user_token_account: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        constraint = pool_token_account.mint == pool.staked_token_mint
    )]
    pub pool_token_account: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.staked_token_mint.as_ref()],
        bump = pool.bump
    )]
    pub pool: Account<'info, Pool>,
    
    #[account(
        mut,
        seeds = [b"user_stake", user.key().as_ref(), pool.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,
    
    #[account(
        mut,
        constraint = user_reward_account.mint == pool.reward_token_mint
    )]
    pub user_reward_account: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub reward_token_mint: Account<'info, Mint>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct UpdateRewardRate<'info> {
    #[account(
        mut,
        seeds = [b"pool", pool.staked_token_mint.as_ref()],
        bump = pool.bump,
        constraint = pool.authority == authority.key()
    )]
    pub pool: Account<'info, Pool>,
    
    pub authority: Signer<'info>,
}

#[error_code]
pub enum StakingError {
    #[msg("Insufficient stake")]
    InsufficientStake,
    #[msg("No rewards to claim")]
    NoRewards,
    #[msg("Math overflow")]
    MathOverflow,
}

use anchor_spl::token::{self, Mint, Token, TokenAccount};
