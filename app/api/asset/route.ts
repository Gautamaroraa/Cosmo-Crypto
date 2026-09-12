/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextRequest,NextResponse } from "next/server";

const strip=(html:string)=>html.replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim();
const chainIds:Record<string,string>={ethereum:"1","binance-smart-chain":"56","polygon-pos":"137","arbitrum-one":"42161","optimistic-ethereum":"10",base:"8453",avalanche:"43114",fantom:"250"};

export async function GET(request:NextRequest){
  const id=request.nextUrl.searchParams.get("id");
  if(!id||!/^[a-z0-9-]+$/.test(id))return NextResponse.json({error:"Invalid asset"},{status:400});
  try{
    const coinResponse=await fetch(`https://api.coingecko.com/api/v3/coins/${id}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=true&sparkline=true`,{headers:{accept:"application/json"},next:{revalidate:300}});
    if(!coinResponse.ok)throw new Error(`Asset provider returned ${coinResponse.status}`);
    const coin=await coinResponse.json() as any;
    const protocolsResponse=await fetch("https://api.llama.fi/protocols",{next:{revalidate:900}});
    const protocols=protocolsResponse.ok?await protocolsResponse.json() as any[]:[];
    const protocol=protocols.find(p=>p.symbol?.toLowerCase()===coin.symbol?.toLowerCase()&&(p.name?.toLowerCase()===coin.name?.toLowerCase()||p.tvl));
    const platformEntry=Object.entries(coin.platforms??{}).find(([platform,address])=>chainIds[platform]&&address);
    let security:null|Record<string,any>=null;
    if(platformEntry){const [platform,address]=platformEntry;const securityResponse=await fetch(`https://api.gopluslabs.io/api/v1/token_security/${chainIds[platform]}?contract_addresses=${address}`,{next:{revalidate:3600}});if(securityResponse.ok){const payload=await securityResponse.json() as any;security=payload.result?.[(address as string).toLowerCase()]??payload.result?.[address as string]??null}}
    const md=coin.market_data??{},dev=coin.developer_data??{},community=coin.community_data??{};
    const riskFlags:string[]=[];
    if(md.max_supply&&md.circulating_supply/md.max_supply<.5)riskFlags.push("More than half of maximum supply is not yet circulating");
    if((md.total_volume?.usd??0)/(md.market_cap?.usd??1)<.01)riskFlags.push("Daily turnover is below 1% of market capitalisation");
    if((md.ath_change_percentage?.usd??0)<-75)riskFlags.push("Price remains more than 75% below its all-time high");
    if(security?.is_honeypot==="1")riskFlags.push("Contract scan indicates honeypot behaviour");
    if(security?.mintable==="1")riskFlags.push("Contract owner may be able to mint additional tokens");
    if(security?.hidden_owner==="1")riskFlags.push("Contract scan reports a hidden owner");
    return NextResponse.json({id:coin.id,name:coin.name,symbol:coin.symbol?.toUpperCase(),image:coin.image?.large,description:strip(coin.description?.en??"").slice(0,1400),categories:coin.categories??[],genesisDate:coin.genesis_date,links:{homepage:coin.links?.homepage?.find(Boolean)??null,explorer:coin.links?.blockchain_site?.find(Boolean)??null,github:coin.links?.repos_url?.github?.[0]??null},market:{price:md.current_price?.usd,marketCap:md.market_cap?.usd,rank:coin.market_cap_rank,fdv:md.fully_diluted_valuation?.usd,volume24h:md.total_volume?.usd,high24h:md.high_24h?.usd,low24h:md.low_24h?.usd,ath:md.ath?.usd,athChange:md.ath_change_percentage?.usd,athDate:md.ath_date?.usd,atl:md.atl?.usd,atlChange:md.atl_change_percentage?.usd},supply:{circulating:md.circulating_supply,total:md.total_supply,max:md.max_supply},performance:{h24:md.price_change_percentage_24h??null,d7:md.price_change_percentage_7d??null,d14:md.price_change_percentage_14d??null,d30:md.price_change_percentage_30d??null,d60:md.price_change_percentage_60d??null,d200:md.price_change_percentage_200d??null,y1:md.price_change_percentage_1y??null},developer:{stars:dev.stars??null,forks:dev.forks??null,subscribers:dev.subscribers??null,totalIssues:dev.total_issues??null,closedIssues:dev.closed_issues??null,pullRequestsMerged:dev.pull_requests_merged??null,commitCount4Weeks:dev.commit_count_4_weeks??null},community:{twitterFollowers:community.twitter_followers??null,redditSubscribers:community.reddit_subscribers??null,telegramUsers:community.telegram_channel_user_count??null},protocol:protocol?{name:protocol.name,tvl:protocol.tvl,category:protocol.category,chains:protocol.chains??[],change1d:protocol.change_1d,change7d:protocol.change_7d,fees30d:protocol.fees_30d??null,revenue30d:protocol.revenue_30d??null}:null,security:security?{platform:platformEntry?.[0],holderCount:security.holder_count??null,isHoneypot:security.is_honeypot==="1",mintable:security.mintable==="1",proxy:security.is_proxy==="1",hiddenOwner:security.hidden_owner==="1",ownershipRenounced:security.owner_address==="",buyTax:security.buy_tax??null,sellTax:security.sell_tax??null}:null,riskFlags,sparkline:md.sparkline_7d?.price??[],updatedAt:coin.last_updated},{headers:{"Cache-Control":"public, s-maxage=300, stale-while-revalidate=600"}});
  }catch(error){return NextResponse.json({error:error instanceof Error?error.message:"Unable to build report"},{status:503})}
}
