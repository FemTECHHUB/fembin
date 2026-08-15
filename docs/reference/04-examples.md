# 04 — Example requests

All examples are HTTP `GET http://<host>:981` with the listed **headers**.
`UserName`/`Pwd` are required on every call.

## 4.1 Run a SQL query (SC=1)

```
SC:       1
Qry:      Select * from Tran1 where VchType=9
UserName: a
Pwd:      a
```
Returns the recordset as XML in the response body. `Tran1` is the transactions table.

## 4.2 Add an Account master (SC=5, MasterType=2)

Minimal:
```xml
<Account><Name>Acc1</Name><ParentGroup>Sundry Creditors</ParentGroup></Account>
```
Full (from the Postman collection):
```xml
<Account>
  <Name>Hemant Bhatt</Name>
  <Alias>Hemant</Alias>
  <PrintName>Hemant Bhatt</PrintName>
  <ParentGroup>Sundry Debtors</ParentGroup>
  <BillByBillBalancing>True</BillByBillBalancing>
  <Address>
    <Address1>Model Town</Address1><Address2>Delhi</Address2>
    <Mobile>8282828282</Mobile><WhatsAppNo>918282828282</WhatsAppNo>
    <ITPAN>782837BN34</ITPAN><GSTNo>07782837BN34224322</GSTNo>
    <CountryName>India</CountryName><StateName>Delhi</StateName><AreaName>---Others---</AreaName>
  </Address>
  <TypeOfDealerGST>Registered</TypeOfDealerGST>
</Account>
```
On success the body returns the newly generated **Master Code**.

## 4.3 Add a Sale voucher (SC=2, VchType=9)

Item‑based vouchers use `<ItemEntries>`. Note BUSY expects **pre‑calculated** tax/net/amounts —
it does not compute them for you.
```xml
<Sale>
  <VchSeriesName>Main</VchSeriesName>
  <Date>01-04-2024</Date>
  <VchType>9</VchType>
  <VchNo>1</VchNo>
  <STPTName>Local-ItemWise</STPTName>
  <MasterName1>Customer-Amit Gupta</MasterName1>   <!-- party account -->
  <MasterName2>Main Store</MasterName2>            <!-- material center -->
  <ItemEntries>
    <ItemDetail>
      <SrNo>1</SrNo><ItemName>Acer Laptop</ItemName><UnitName>Pcs.</UnitName>
      <Qty>1</Qty><Price>26000</Price><Amt>30680</Amt>
      <ItemTaxCategory>GST 18%</ItemTaxCategory>
      <STAmount>4680</STAmount><STPercent>9</STPercent><STPercent1>9</STPercent1>
      <MC>Main Store</MC>
    </ItemDetail>
  </ItemEntries>
  <BillSundries>
    <BSDetail><SrNo>1</SrNo><BSName>Discount</BSName><PercentVal>2</PercentVal><Amt>1203.6</Amt></BSDetail>
  </BillSundries>
</Sale>
```
On success the body returns the newly generated **Voucher Code**.

## 4.4 Accounting vouchers — Journal / Payment / Receipt

These use `<AccEntries>` instead of `<ItemEntries>`. `AmountType` = **1 (Debit)** / **2 (Credit)**.

Journal (VchType=16):
```xml
<Journal>
  <VchSeriesName>Main</VchSeriesName><Date>01-04-2023</Date><VchType>16</VchType>
  <AccEntries>
    <AccDetail><SrNo>1</SrNo><AccountName>Busy Infotech Pvt. Ltd.</AccountName><AmountType>2</AmountType><AmtMainCur>5000</AmtMainCur></AccDetail>
    <AccDetail><SrNo>2</SrNo><AccountName>Travelling Expenses</AccountName><AmountType>1</AmountType><AmtMainCur>2000</AmtMainCur></AccDetail>
  </AccEntries>
</Journal>
```

Receipt (VchType=14) — money received from a customer:
```xml
<Receipt>
  <VchSeriesName>Main</VchSeriesName><Date>01-04-2023</Date><VchType>14</VchType><VchNo>1</VchNo>
  <AccEntries>
    <AccDetail><SrNo>1</SrNo><AccountName>Customer-Amit Gupta</AccountName><AmountType>2</AmountType><AmtMainCur>120</AmtMainCur></AccDetail>
    <AccDetail><SrNo>2</SrNo><AccountName>Cash</AccountName><AmountType>1</AmountType><AmtMainCur>120</AmtMainCur></AccDetail>
  </AccEntries>
</Receipt>
```

## 4.5 Retrieve a voucher (SC=8)

```
SC:       8
VchCode:  40018
UserName: a
Pwd:      a
```
Body → the voucher's XML (same format you'd send back to modify it). Useful to **verify a
posted sale actually saved**.

## 4.6 Reference call pattern (from the VB.NET sample)

```vb
UrlStr = "http://<host>:981"
req = WebRequest.Create(UrlStr)
req.Method = "GET"

h = New WebHeaderCollection
h.Add("SC", "2")            ' service code
h.Add("VchType", "9")       ' Sale
h.Add("VchXML", XMLStr)     ' entire XML passed as a header value
h.Add("UserName", user)
h.Add("Pwd", pwd)
req.Headers = h

res = req.GetResponse()
If res.GetResponseHeader("Result") = "T" Then
    ' body = new VchCode
Else
    ' res.GetResponseHeader("Description") = error message
End If
```
The same thing in any language: HTTP GET to the BUSY port, all params (incl. XML) as headers,
then read the `Result` header and the body.
