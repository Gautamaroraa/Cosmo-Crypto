import { NextResponse } from "next/server";

type GeckoAsset = { id:string;symbol:string;name:string;image:string;current_price:number;market_cap:number;market_cap_rank:number;fully_diluted_valuation:number|null;total_volume:number;high_24h:number;low_24h:number;price_change_percentage_24h:number;price_change_percentage_7d_in_currency:number|null;price_change_percentage_30d_in_currency:number|null;circulating_supply:number|null;total_supply:number|null;max_supply:number|null;ath:number;ath_change_percentage:number;atl:number;last_updated:string };
type CmcAsset={symbol:string;quote:{USD:{price:number}}};
type Protocol={name:string;symbol?:string;slug?:string;tvl?:number;category?:string;chains?:string[];change_1d?:number;change_7d?:number};
const clamp=(v:number,min:number,max:number)=>Math.min(max,Math.max(min,v));

function scoreAsset(asset:GeckoAsset,protocol?:Protocol){
  const market=clamp(Math.round(21-Math.log2(Math.max(asset.market_cap_rank,1))*2.7),3,20);
  const volumeRatio=asset.market_cap?asset.total_volume/asset.market_cap:0;
  const liquidity=clamp(Math.round(6+Math.min(volumeRatio*70,9)),4,15);
  const issued=asset.max_supply&&asset.circulating_supply?asset.circulating_supply/asset.max_supply:null;
  const tokenomics=issued===null?11:clamp(Math.round(6+issued*14),5,20);
  const resilience=clamp(Math.round(10-Math.max(0,Math.abs(asset.price_change_percentage_30d_in_currency??0)-12)/9),3,10);
  const adoption=protocol?.tvl?clamp(Math.round(4+Math.log10(Math.max(protocol.tvl,1))*1.25),5,15):7;
  const drawdown=Math.abs(asset.ath_change_percentage??0);
  const marketHistory=clamp(Math.round(10-Math.max(0,drawdown-55)/15),4,10);
  const confidence=[asset.current_price,asset.market_cap,asset.total_volume,asset.circulating_supply,asset.last_updated].filter(v=>v!==null&&v!==undefined).length*2;
  const total=market+liquidity+tokenomics+resilience+adoption+marketHistory+confidence;
  const risk:"Low"|"Moderate"|"High"=total>=80?"Low":total>=60?"Moderate":"High";
  return {score:total,risk,parts:[
    {label:"Market strength",score:market,max:20,note:`#${asset.market_cap_rank} by market capitalisation`},
    {label:"Liquidity",score:liquidity,max:15,note:`${(volumeRatio*100).toFixed(2)}% daily turnover`},
    {label:"Tokenomics",score:tokenomics,max:20,note:issued===null?"No fixed maximum supply reported":`${(issued*100).toFixed(1)}% of maximum supply circulating`},
    {label:"Resilience",score:resilience,max:10,note:`${Math.abs(asset.price_change_percentage_30d_in_currency??0).toFixed(1)}% absolute 30-day move`},
    {label:"Protocol adoption",score:adoption,max:15,note:protocol?.tvl?`$${Math.round(protocol.tvl).toLocaleString()} protocol TVL`:"No matched DeFi protocol TVL"},
    {label:"Cycle position",score:marketHistory,max:10,note:`${drawdown.toFixed(1)}% below all-time high`},
    {label:"Data confidence",score:confidence,max:10,note:"Core market fields independently checked"}
  ]};
}

export async function GET(){
  try{
    const geckoUrl="https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=7d%2C30d";
    const [geckoResponse,cmcResponse,llamaResponse]=await Promise.all([
      fetch(geckoUrl,{headers:{accept:"application/json"},next:{revalidate:60}}),
      fetch("https://pro-api.coinmarketcap.com/public-api/v1/cryptocurrency/listings/latest?start=1&limit=100&convert=USD",{headers:{accept:"application/json"},next:{revalidate:60}}),
      fetch("https://api.llama.fi/protocols",{headers:{accept:"application/json"},next:{revalidate:900}})
    ]);
    if(!geckoResponse.ok)throw new Error(`Market provider returned ${geckoResponse.status}`);
    const gecko=await geckoResponse.json() as GeckoAsset[];
    const cmc=cmcResponse.ok?(await cmcResponse.json() as {data:CmcAsset[]}).data:[];
    const protocols=llamaResponse.ok?await llamaResponse.json() as Protocol[]:[];
    const cmcBySymbol=new Map(cmc.map(a=>[a.symbol.toUpperCase(),a]));
    const protocolBySymbol=new Map<string,Protocol>();
    for(const protocol of protocols)if(protocol.symbol&&!protocolBySymbol.has(protocol.symbol.toUpperCase()))protocolBySymbol.set(protocol.symbol.toUpperCase(),protocol);
    const assets=gecko.map(asset=>{
      const protocol=protocolBySymbol.get(asset.symbol.toUpperCase());
      const cmcPrice=cmcBySymbol.get(asset.symbol.toUpperCase())?.quote.USD.price??null;
      const spread=cmcPrice&&asset.current_price?Math.abs(cmcPrice-asset.current_price)/asset.current_price*100:null;
      return {id:asset.id,name:asset.name,symbol:asset.symbol.toUpperCase(),image:asset.image,rank:asset.market_cap_rank,price:asset.current_price,marketCap:asset.market_cap,fullyDilutedValuation:asset.fully_diluted_valuation,volume24h:asset.total_volume,high24h:asset.high_24h,low24h:asset.low_24h,change24h:asset.price_change_percentage_24h,change7d:asset.price_change_percentage_7d_in_currency,change30d:asset.price_change_percentage_30d_in_currency,circulatingSupply:asset.circulating_supply,totalSupply:asset.total_supply,maxSupply:asset.max_supply,ath:asset.ath,athChange:asset.ath_change_percentage,atl:asset.atl,lastUpdated:asset.last_updated,tvl:protocol?.tvl??null,category:protocol?.category??null,chains:protocol?.chains??[],providerPrices:{coinGecko:asset.current_price,coinMarketCap:cmcPrice,spreadPct:spread},...scoreAsset(asset,protocol)};
    });
    return NextResponse.json({assets,updatedAt:gecko[0]?.last_updated??new Date().toISOString(),source:cmc.length?"CoinGecko + CMC + DefiLlama":"CoinGecko + DefiLlama",autoRefreshSeconds:60},{headers:{"Cache-Control":"public, s-maxage=60, stale-while-revalidate=120"}});
  }catch(error){return NextResponse.json({error:error instanceof Error?error.message:"Market feed unavailable"},{status:503,headers:{"Cache-Control":"no-store"}})}
}
